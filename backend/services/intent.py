import time
from decimal import Decimal

import anthropic
from loguru import logger

from backend.config import backend_settings
from backend.metrics import llm_call_duration, llm_errors, observe_token_usage
from backend.schemas.recommendation import IntentResult, IntentType
from backend.services._anthropic import get_anthropic_client
from core.categories import CATEGORY_FAMILIES, CATEGORY_GROUPS

_MODEL = "claude-haiku-4-5-20251001"


def _build_category_reference() -> str:
    """Build category reference for the system prompt from the wine taxonomy."""
    lines: list[str] = []
    for group_key in CATEGORY_FAMILIES["vins"].children:
        group = CATEGORY_GROUPS[group_key]
        prefixes = ", ".join(f'"{p}"' for p in group.prefixes)
        lines.append(f"- {group.label}: {prefixes}")
    return "\n".join(lines)


_CATEGORY_REFERENCE = _build_category_reference()

_SYSTEM_PROMPT = f"""\
You are a wine assistant for the SAQ catalog (Québec wine stores).
Given a user query (French or English), decide which tool to call:

- **search_wines**: the user wants specific product recommendations — bottles to buy, \
wines to try, gift ideas, "surprise me", anything that expects product results.
- **wine_chat**: the user wants general wine knowledge — grape info, region facts, \
food pairing explanations, winemaking, comparisons, tasting tips, wine culture. \
No specific products requested.
- **off_topic**: the user asks about something unrelated to wine — beer, spirits, \
food, weather, tech, etc.

## Examples
- "un rouge fruité autour de 25$" → search_wines
- "surprise me" → search_wines (open-ended but wants products)
- "recommend a wine for my date tonight" → search_wines
- "what pairs with lamb?" → wine_chat (wants pairing knowledge, not a bottle)
- "tell me about Burgundy" → wine_chat (wants region info)
- "difference between Syrah and Shiraz?" → wine_chat
- "do you have beer?" → off_topic
- "I want a gin" → off_topic

## Category reference (SAQ naming)
{_CATEGORY_REFERENCE}

## search_wines rules
1. **Always pick categories.** Infer from context when not explicit:
   - Food pairing → appropriate wine types (e.g. cheese → Vin rouge, Vin blanc; steak → Vin rouge)
   - Occasion → appropriate types (e.g. "festif léger" → Vin mousseux, Vin rosé, Vin blanc)
   - "sparkling for a celebration" → Champagne, Vin mousseux
   - Only leave categories empty if the query is genuinely open-ended ("surprise me")
2. **Avoid dessert/fortified unless explicitly requested.** "Vin de dessert", "Vin de glace",
   "Porto", "Muscat", "Saké" are specialty categories — only include them if the user asks for
   dessert wine, fortified wine, port, sake, etc. Default to table wines.
3. **Country**: "France", "Italie", "Espagne", "Canada", "États-Unis",
   "Argentine", "Grèce", "Autriche", etc.
   Only set country when the user specifies the wine's origin.
   Food origin doesn't imply wine origin
   (e.g. "tacos al pastor" → no country; "un vin espagnol" → "Espagne").
   When a specific wine is referenced (e.g. "Sassicaia"), set its country.
4. **Price heuristics**:
   - "autour de 25$" → min ~20% below, max ~20% above
   - "moins de 30$" / "under 30" / "sans dépasser 50$" → max_price only
   - "plus de 50$" → min_price only
   - "money is not an issue" → set min_price to 40 (skip budget wines)
   - Large group / volume implied (e.g. "BBQ 20 personnes") →
     set max_price ~25 (crowd-friendly budget)
   - Beginner / "I don't know wine" / restaurant context with no price cue →
     set min_price to 15, max_price to 35 (safe, respectable range)
5. **semantic_query** captures taste, occasion, style, food pairing — whatever can't be a filter.
   Make it descriptive and specific. Include what the user WANTS, not what they don't want.
   Always include concrete grape variety names that match the desired style — embeddings
   contain grape names, so "Gewürztraminer, Riesling" retrieves better than "off-dry, floral".
   - "un rouge fruité autour de 25$" → "fruité, souple, facile à boire, Gamay, Grenache"
   - "bold tannic wine for steak" → "bold tannic full-bodied, Malbec, Syrah, Cabernet Franc"
   - "tired of Pinot Grigio" → semantic_query: "Albariño, Vermentino,
     Grüner Veltliner", exclude_grapes: ["Pinot Grigio", "Pinot Gris"]
   - "like Barolo but lighter" → "elegant Nebbiolo, silky tannins, Langhe"
   - "blancs doux mais pas liquoreux" → "demi-sec, off-dry,
     Gewürztraminer, Riesling, Chenin Blanc, Vouvray"
   - "cadeaux pour un amateur" → "terroir-driven, estate wine, elegant"
   - When food has a regional identity, mention regional pairing in semantic_query
     ("what grows together goes together"). Do NOT set country — let embedding handle it.
     Example: "sushi tonight" → include "crisp, high-acid, Muscadet,
     Chablis, Albariño" in semantic_query
6. **exclude_grapes**: when the user expresses fatigue or dislike for specific
   grapes, ALWAYS populate this field. Look for cues like "tanné de",
   "tired of", "pas de", "no more", "autre chose que".
   - "j'en ai marre du Chardonnay" → exclude_grapes: ["Chardonnay"]
   - "no more Pinot Noir" → exclude_grapes: ["Pinot Noir"]
   Also list appealing alternatives in semantic_query
   (Syrah, Grenache, Tempranillo, Nebbiolo, Gamay, etc.).
Always output category and country values in French (SAQ naming)."""

_TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "search_wines",
        "description": "User wants product recommendations — extract search filters",
        "input_schema": {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "SAQ category names to filter by (e.g. ['Vin rouge'])",
                },
                "min_price": {
                    "type": "number",
                    "description": "Minimum price in CAD, or null",
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum price in CAD, or null",
                },
                "country": {
                    "type": "string",
                    "description": "Country of origin in French, or null",
                },
                "semantic_query": {
                    "type": "string",
                    "description": "Taste/occasion/style intent for semantic search",
                },
                "exclude_grapes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grape varieties to exclude",
                },
            },
            "required": ["semantic_query"],
        },
    },
    {
        "name": "wine_chat",
        "description": (
            "User wants general wine knowledge — grape info, region facts, "
            "food pairings, winemaking, comparisons, tasting tips"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Brief summary of what the user wants to know",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "off_topic",
        "description": "User asks about something unrelated to wine (beer, spirits, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

# Tool name → IntentResult.intent_type
_TOOL_INTENT_MAP: dict[str, IntentType] = {
    "search_wines": "recommendation",
    "wine_chat": "wine_chat",
    "off_topic": "off_topic",
}


async def parse_intent(query: str, conversation_history: str | None = None) -> IntentResult:
    """Classify a user query and extract search filters if applicable.

    Claude picks one of three tools (search_wines, wine_chat, off_topic).
    Falls back to recommendation with raw query as semantic search on failure.
    """
    if not backend_settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning raw query as semantic search")
        return IntentResult(semantic_query=query)

    client = get_anthropic_client()

    if conversation_history:
        content = f"Prior conversation:\n{conversation_history}\n\nNew query: {query}"
    else:
        content = query
    messages: list[anthropic.types.MessageParam] = [{"role": "user", "content": content}]

    try:
        t0 = time.monotonic()
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=256,
            temperature=0,
            system=_SYSTEM_PROMPT,
            messages=messages,
            tools=_TOOLS,
            tool_choice={"type": "auto"},
        )
        llm_call_duration.labels(service="intent").observe(time.monotonic() - t0)
    except anthropic.APIError as exc:
        logger.opt(exception=exc).warning(
            "Claude intent parsing failed — falling back to raw query"
        )
        llm_errors.labels(service="intent").inc()
        return IntentResult(semantic_query=query)

    observe_token_usage("intent", response)

    for block in response.content:
        if block.type == "tool_use" and block.name in _TOOL_INTENT_MAP:
            intent_type = _TOOL_INTENT_MAP[block.name]
            if block.name == "search_wines":
                result = _parse_search_input(block.input, query, intent_type)
            else:
                result = IntentResult(intent_type=intent_type, semantic_query=query)
            logger.debug("Intent classified: {} — {}", intent_type, result)
            return result

    # tool_choice=auto may return text without a tool call — route to sommelier
    logger.warning("Claude returned no tool_use block — falling back to wine_chat")
    return IntentResult(intent_type="wine_chat", semantic_query=query)


def _parse_search_input(
    tool_input: dict, original_query: str, intent_type: IntentType
) -> IntentResult:
    """Convert Claude's search_wines tool input into an IntentResult."""
    try:
        return IntentResult(
            intent_type=intent_type,
            categories=tool_input.get("categories", []),
            min_price=(
                Decimal(str(tool_input["min_price"]))
                if tool_input.get("min_price") is not None
                else None
            ),
            max_price=(
                Decimal(str(tool_input["max_price"]))
                if tool_input.get("max_price") is not None
                else None
            ),
            country=tool_input.get("country"),
            semantic_query=tool_input.get("semantic_query", original_query),
            exclude_grapes=tool_input.get("exclude_grapes", []),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse tool input: {} — falling back to raw query", exc)
        return IntentResult(semantic_query=original_query)

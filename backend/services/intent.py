from decimal import Decimal

import anthropic
from core.categories import CATEGORY_FAMILIES, CATEGORY_GROUPS
from loguru import logger

from backend.config import backend_settings
from backend.schemas.recommendation import IntentResult

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
You are a sommelier search assistant for SAQ (Société des alcools du Québec).
Given a user query (French or English), extract structured search filters for a wine catalog.
Always output category and country values in French (SAQ naming).

## Category reference (SAQ naming)
{_CATEGORY_REFERENCE}

## Rules

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
   (e.g. "fromages québécois" → no country; "un vin espagnol" → "Espagne").
   When a specific wine is referenced (e.g. "Tignanello"), set its country.
4. **Price heuristics**:
   - "autour de 25$" → min ~20% below, max ~20% above
   - "moins de 30$" / "under 30" → max_price only
   - "plus de 50$" → min_price only
   - "money is not an issue" → set min_price to 40 (skip budget wines)
   - Large group / volume implied (e.g. "30 personnes") → set max_price ~25 (crowd-friendly budget)
5. **semantic_query** captures taste, occasion, style, food pairing — whatever can't be a filter.
   Make it descriptive and specific. Include what the user WANTS, not what they don't want.
   - "un rouge fruité autour de 25$" → "fruité, souple, facile à boire"
   - "bold tannic wine for steak" → "bold tannic full-bodied for grilled steak"
   - "tanné du Cab Sauv" → semantic_query: "Syrah, Grenache, Tempranillo",
     exclude_grapes: ["Cabernet Sauvignon", "Merlot"]
   - "like Sancerre but cheaper" → "crisp minerally Sauvignon Blanc style, Loire-like freshness"
   - "moscato trop sucré, compromis" → "demi-sec, off-dry, floral aromatic"
6. **exclude_grapes**: when the user expresses fatigue or dislike for specific
   grapes, ALWAYS populate this field. Look for cues like "tanné de",
   "tired of", "pas de", "no more", "autre chose que".
   - "tanné du Cab Sauv et du Merlot" → exclude_grapes: ["Cabernet Sauvignon", "Merlot"]
   - "qqch de différent, pas de Chardonnay" → exclude_grapes: ["Chardonnay"]
   Also list appealing alternatives in semantic_query
   (Syrah, Grenache, Tempranillo, Nebbiolo, Gamay, etc.).
7. **Non-wine queries** (beer, spirits, etc.): still call the tool, but set categories to an empty
   list and semantic_query to the original query. The system handles graceful fallback.

Always call the search_wines tool with your extraction."""

_TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "search_wines",
        "description": "Extract structured search filters from a wine query",
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
                    "description": "Country of origin, or null",
                },
                "available_only": {
                    "type": "boolean",
                    "description": "Whether to only show available products (default true)",
                },
                "semantic_query": {
                    "type": "string",
                    "description": "Remaining taste/occasion/style intent for semantic search",
                },
                "exclude_grapes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grape varieties to exclude",
                },
            },
            "required": ["semantic_query"],
        },
    }
]


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=backend_settings.ANTHROPIC_API_KEY)
    return _client


def parse_intent(query: str) -> IntentResult:
    """Extract structured search filters from a natural language wine query.

    Uses Claude Haiku with forced tool_use to return structured filters.
    Falls back to semantic-only search if Claude call fails.
    """
    if not backend_settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning raw query as semantic search")
        return IntentResult(semantic_query=query)

    client = _get_client()

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=128,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": query}],
            tools=_TOOLS,
            tool_choice={"type": "tool", "name": "search_wines"},
        )
    except anthropic.APIError as exc:
        logger.opt(exception=exc).warning(
            "Claude intent parsing failed — falling back to raw query"
        )
        return IntentResult(semantic_query=query)

    for block in response.content:
        if block.type == "tool_use" and block.name == "search_wines":
            result = _parse_tool_input(block.input, query)
            logger.debug("Intent parsed: {}", result)
            return result

    logger.warning("Claude returned no tool_use block — falling back to raw query")
    return IntentResult(semantic_query=query)


def _parse_tool_input(tool_input: dict, original_query: str) -> IntentResult:
    """Convert Claude's tool_use input dict into an IntentResult."""
    try:
        return IntentResult(
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
            available_only=tool_input.get("available_only", True),
            semantic_query=tool_input.get("semantic_query", original_query),
            exclude_grapes=tool_input.get("exclude_grapes", []),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse tool input: {} — falling back to raw query", exc)
        return IntentResult(semantic_query=original_query)

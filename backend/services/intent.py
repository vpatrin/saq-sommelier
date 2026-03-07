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
You are a search filter extractor for an SAQ (Société des alcools du Québec) wine catalog.
Given a user query about wine (in French or English), extract structured search filters.
Always output category and country values in French (SAQ naming), regardless of query language.

Category values must use SAQ naming (use the prefix that best matches):
{_CATEGORY_REFERENCE}

Country values: "France", "Italie", "Espagne", "Canada", "États-Unis", "Argentine", etc.

For price signals like "autour de 25$", set min_price ~20% below and max_price ~20% above.
For "moins de 30$" or "under 30", only set max_price.
For "plus de 50$", only set min_price.

The semantic_query should capture the taste/occasion/style intent — the part that
can't be expressed as a structured filter. Examples:
- "un rouge fruité autour de 25$" → semantic_query: "fruité"
- "bold tannic wine for steak" → semantic_query: "bold tannic for steak"
- "surprise me" → semantic_query: "surprise me, something interesting"

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
                Decimal(str(tool_input["min_price"])) if tool_input.get("min_price") else None
            ),
            max_price=(
                Decimal(str(tool_input["max_price"])) if tool_input.get("max_price") else None
            ),
            country=tool_input.get("country"),
            available_only=tool_input.get("available_only", True),
            semantic_query=tool_input.get("semantic_query", original_query),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse tool input: {} — falling back to raw query", exc)
        return IntentResult(semantic_query=original_query)

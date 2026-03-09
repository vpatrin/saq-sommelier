import anthropic
from core.db.models import Product
from loguru import logger

from backend.config import backend_settings
from backend.schemas.recommendation import IntentResult

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """\
You are a wine sommelier assistant helping users discover wines from the SAQ catalog.
Given a user's wine query and a list of recommended wines, explain why each wine
was selected and write a short summary of the selection.

## Rules
1. Write in the same language as the user query (French or English).
2. Each reason should be 1 sentence, specific to the wine and the query.
   Reference concrete attributes (grape, region, taste profile, price) — not generic praise.
3. The summary should be 1-2 sentences tying the selection together.
4. If the query mentions food pairing, occasion, or budget, reference it in the reasons.

Always call the explain tool with your output."""

_TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "explain",
        "description": "Provide per-wine reasons and an overall summary",
        "input_schema": {
            "type": "object",
            "properties": {
                "reasons": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "One reason per wine, in the same order as the input list",
                },
                "summary": {
                    "type": "string",
                    "description": "1-2 sentence overview of the recommendation set",
                },
            },
            "required": ["reasons", "summary"],
        },
    }
]


def _format_wine(idx: int, product: Product) -> str:
    parts = [f"{idx + 1}. {product.name}"]
    if product.grape:
        parts.append(f"Grape: {product.grape}")
    if product.region:
        parts.append(f"Region: {product.region}")
    if product.country:
        parts.append(f"Country: {product.country}")
    if product.price:
        parts.append(f"Price: {product.price}$")
    if product.taste_tag:
        parts.append(f"Taste: {product.taste_tag}")
    return " | ".join(parts)


def _build_user_message(query: str, intent: IntentResult, products: list[Product]) -> str:
    wines = "\n".join(_format_wine(i, p) for i, p in enumerate(products))
    return f"Query: {query}\n\nRecommended wines:\n{wines}"


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=backend_settings.ANTHROPIC_API_KEY)
    return _client


class ExplanationResult:
    __slots__ = ("reasons", "summary")

    def __init__(self, reasons: list[str], summary: str) -> None:
        self.reasons = reasons
        self.summary = summary


def explain_recommendations(
    query: str,
    intent: IntentResult,
    products: list[Product],
) -> ExplanationResult:
    """Generate per-product reasons and a summary for a recommendation set."""
    n = len(products)
    if n == 0:
        return ExplanationResult(reasons=[], summary="")

    if not backend_settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — skipping curation")
        return _fallback(n)

    client = _get_client()
    user_msg = _build_user_message(query, intent, products)

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            temperature=backend_settings.HAIKU_TEMPERATURE,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            tools=_TOOLS,
            tool_choice={"type": "tool", "name": "explain"},
        )
    except anthropic.APIError as exc:
        logger.opt(exception=exc).warning("Curation call failed — using fallback")
        return _fallback(n)

    for block in response.content:
        if block.type == "tool_use" and block.name == "explain":
            return _parse_tool_input(block.input, n)

    logger.warning("No tool_use block in curation response — using fallback")
    return _fallback(n)


def _parse_tool_input(tool_input: dict, expected_count: int) -> ExplanationResult:
    reasons = tool_input.get("reasons", [])
    summary = tool_input.get("summary", "")
    # Pad or truncate reasons to match product count
    if len(reasons) < expected_count:
        reasons.extend([""] * (expected_count - len(reasons)))
    elif len(reasons) > expected_count:
        reasons = reasons[:expected_count]
    return ExplanationResult(reasons=reasons, summary=summary)


def _fallback(n: int) -> ExplanationResult:
    return ExplanationResult(reasons=[""] * n, summary="")

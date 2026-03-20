import time

import anthropic
from loguru import logger

from backend.config import backend_settings
from backend.metrics import llm_call_duration, llm_errors, observe_token_usage
from backend.services._anthropic import get_anthropic_client

_MODEL = "claude-haiku-4-5-20251001"

_MAX_TOKENS = 512

_FALLBACK_MESSAGE = "I'm having trouble connecting right now — try again in a moment."

_SYSTEM_PROMPT = """\
You are a knowledgeable wine sommelier. You help users learn about wine — \
grape varieties, regions, food pairings, tasting technique, winemaking, \
comparisons, and general wine culture.

## Rules
1. Write in the same language as the user (French or English).
2. Be conversational and warm, but concise — prefer 2-4 short paragraphs over walls of text.
3. When comparing wines, use concrete attributes (tannin, acidity, body, aroma) not vague praise.
4. You may reference SAQ as a source of wines available in Québec, but do NOT recommend \
specific products by name or SKU — the recommendation system handles that separately. \
If the user asks for a specific product suggestion, tell them to ask for a recommendation instead.
5. For food pairings, explain WHY the pairing works \
(acidity cuts fat, tannin matches protein, etc.).
6. If the question is not about wine, politely redirect — you're a wine specialist."""


def _build_messages(
    query: str,
    *,
    conversation_history: str | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if conversation_history:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Previous conversation:\n{conversation_history}\n\nNew question: {query}"
                ),
            }
        )
    else:
        messages.append({"role": "user", "content": query})
    return messages


async def sommelier_chat(
    query: str,
    *,
    conversation_history: str | None = None,
) -> str:
    """Answer a freeform wine question via Claude. Returns plain text."""
    if not backend_settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning fallback")
        return _FALLBACK_MESSAGE

    client = get_anthropic_client()

    try:
        t0 = time.monotonic()
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            temperature=backend_settings.HAIKU_TEMPERATURE,
            system=_SYSTEM_PROMPT,
            messages=_build_messages(query, conversation_history=conversation_history),
        )
        llm_call_duration.labels(service="sommelier").observe(time.monotonic() - t0)
    except anthropic.APIError as exc:
        logger.opt(exception=exc).warning("Sommelier chat call failed — returning fallback")
        llm_errors.labels(service="sommelier").inc()
        return _FALLBACK_MESSAGE

    observe_token_usage("sommelier", response)

    # Extract text from response blocks
    parts = [block.text for block in response.content if block.type == "text"]
    if not parts:
        logger.warning("Sommelier response had no text blocks — returning fallback")
        return _FALLBACK_MESSAGE

    return "\n\n".join(parts)

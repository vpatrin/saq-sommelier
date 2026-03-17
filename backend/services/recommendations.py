import time

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import NON_WINE_MESSAGE
from backend.repositories.recommendations import find_similar
from backend.schemas.product import ProductOut
from backend.schemas.recommendation import (
    IntentResult,
    RecommendationOut,
    RecommendationProductOut,
)
from backend.services._openai import get_openai_client
from backend.services.curation import explain_recommendations
from backend.services.intent import parse_intent
from core.db.models import RecommendationLog
from core.embedding_client import async_embed_query


async def _write_log(
    db: AsyncSession,
    *,
    user_id: str | None,
    query: str,
    parsed_intent: dict | None,
    returned_skus: list[str] | None,
    product_count: int,
    latency_ms: dict | None,
) -> int | None:
    """Write a RecommendationLog row. Returns the log ID, or None on failure.

    Does not commit — get_db handles session lifecycle.
    """
    try:
        log = RecommendationLog(
            user_id=user_id,
            query=query,
            parsed_intent=parsed_intent,
            returned_skus=returned_skus,
            product_count=product_count,
            latency_ms=latency_ms,
        )
        db.add(log)
        await db.flush()
        return log.id
    except Exception as exc:
        logger.opt(exception=exc).warning("Failed to write recommendation log")
        return None


def _time_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


async def recommend(
    db: AsyncSession,
    query: str,
    *,
    user_id: str | None = None,
    exclude_skus: list[str] | None = None,
    conversation_history: str | None = None,
    available_online: bool = True,
    in_store: str | None = None,
    intent: IntentResult | None = None,
) -> RecommendationOut:
    """Full recommendation pipeline: parse intent → embed → retrieve → explain.

    If `intent` is provided (pre-parsed by caller), skip intent parsing.
    """
    t_start = time.monotonic()
    latency: dict[str, int] = {}
    skus: list[str] = []

    try:
        if intent is None:
            t0 = time.monotonic()
            intent = await parse_intent(query)
            latency["intent"] = _time_ms(t0)

        if intent.intent_type != "recommendation":
            return RecommendationOut(products=[], intent=intent, summary=NON_WINE_MESSAGE)

        t0 = time.monotonic()
        vector = await async_embed_query(intent.semantic_query, client=get_openai_client())
        latency["embed"] = _time_ms(t0)

        t0 = time.monotonic()
        products = await find_similar(
            db,
            intent,
            vector,
            exclude_skus=exclude_skus,
            available_online=available_online,
            in_store=in_store,
        )
        latency["search"] = _time_ms(t0)

        t0 = time.monotonic()
        explanation = await explain_recommendations(
            query, products, conversation_history=conversation_history
        )
        latency["curation"] = _time_ms(t0)

        skus = [p.sku for p in products]

        result = RecommendationOut(
            products=[
                RecommendationProductOut(
                    product=ProductOut.model_validate(p),
                    reason=explanation.reasons[i],
                )
                for i, p in enumerate(products)
            ],
            intent=intent,
            summary=explanation.summary,
        )
    except Exception as exc:
        logger.opt(exception=exc).error("Recommendation pipeline failed")
        raise

    latency["total"] = _time_ms(t_start)
    log_id = await _write_log(
        db,
        user_id=user_id,
        query=query,
        parsed_intent=intent.model_dump(mode="json"),
        returned_skus=skus,
        product_count=len(skus),
        latency_ms=latency,
    )
    result.log_id = log_id
    return result

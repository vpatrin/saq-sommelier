import asyncio

import anthropic
from core.db.base import create_session_factory
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.services.recommendations import recommend

from .judge import JUDGE_MODEL, judge_query
from .schemas import (
    DimensionScore,
    EvalReport,
    ParsedIntentSummary,
    ProductSummary,
    QueryScore,
    RubricDimension,
    TestQuery,
)


async def _run_single(
    session_factory: async_sessionmaker[AsyncSession],
    test_query: TestQuery,
) -> tuple[ParsedIntentSummary, list[ProductSummary]]:
    """Run the real recommendation pipeline for one query."""
    async with session_factory() as db:
        result = await recommend(db, test_query.query, available_only=False)

    intent = ParsedIntentSummary(
        categories=result.intent.categories,
        min_price=result.intent.min_price,
        max_price=result.intent.max_price,
        country=result.intent.country,
        available_only=result.intent.available_only,
        semantic_query=result.intent.semantic_query,
    )
    products = [
        ProductSummary(
            sku=p.sku,
            name=p.name,
            category=p.category,
            country=p.country,
            price=p.price,
            producer=p.producer,
            grape=p.grape,
            region=p.region,
            taste_tag=p.taste_tag,
            rating=p.rating,
            review_count=p.review_count,
            online_availability=p.online_availability,
        )
        for p in result.products
    ]
    return intent, products


def _make_error_score(
    test_query: TestQuery,
    dimensions: list[RubricDimension],
    error: str,
) -> QueryScore:
    return QueryScore(
        query_id=test_query.id,
        query=test_query.query,
        scores={
            d.name: DimensionScore(score=1, justification=f"Pipeline error: {error}")
            for d in dimensions
        },
        parsed_intent=ParsedIntentSummary(),
        products=[],
        error=error,
    )


async def run_eval(
    database_url: str,
    anthropic_api_key: str,
    queries: list[TestQuery],
    dimensions: list[RubricDimension],
) -> EvalReport:
    """Run the full eval: pipeline -> judge -> report."""
    session_factory = create_session_factory(database_url)
    judge_client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    # Phase 1: Run pipeline sequentially (each hits Haiku + OpenAI + DB)
    collected: list[tuple[TestQuery, ParsedIntentSummary, list[ProductSummary], str | None]] = []

    for i, test_query in enumerate(queries, 1):
        logger.info("[{}/{}] {}", i, len(queries), test_query.query)
        try:
            intent, products = await _run_single(session_factory, test_query)
            logger.info(
                "  -> {} products | intent: {} {} {}",
                len(products),
                intent.categories,
                f"${intent.max_price}" if intent.max_price else "",
                intent.country or "",
            )
            collected.append((test_query, intent, products, None))
        except Exception as exc:
            logger.opt(exception=exc).error("  Pipeline failed: {}", exc)
            collected.append((test_query, ParsedIntentSummary(), [], str(exc)))

    # Phase 2: Judge in parallel (Sonnet calls are independent)
    logger.info("Judging {} results with {}...", len(collected), JUDGE_MODEL)
    judge_tasks = []
    error_scores: dict[int, QueryScore] = {}

    for test_query, intent, products, error in collected:
        if error:
            error_scores[test_query.id] = _make_error_score(test_query, dimensions, error)
        else:
            judge_tasks.append(judge_query(judge_client, test_query, intent, products, dimensions))

    judged = await asyncio.gather(*judge_tasks) if judge_tasks else []

    # Merge judged + error scores in original order
    judged_iter = iter(judged)
    query_scores: list[QueryScore] = []
    for test_query, *_ in collected:
        if test_query.id in error_scores:
            query_scores.append(error_scores[test_query.id])
        else:
            query_scores.append(next(judged_iter))

    # Phase 3: Compute averages
    averages: dict[str, float] = {}
    for d in dimensions:
        dim_scores = [qs.scores[d.name].score for qs in query_scores if d.name in qs.scores]
        averages[d.name] = round(sum(dim_scores) / len(dim_scores), 2) if dim_scores else 0.0

    total_weight = sum(d.weight for d in dimensions)
    weighted_avg = (
        sum(averages[d.name] * d.weight for d in dimensions) / total_weight
        if total_weight > 0
        else 0.0
    )

    return EvalReport(
        judge_model=JUDGE_MODEL,
        rubric=dimensions,
        total_queries=len(queries),
        query_scores=query_scores,
        averages=averages,
        weighted_average=round(weighted_avg, 2),
    )

import asyncio

import anthropic
from core.db.base import create_session_factory
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.services.recommendations import recommend

from .judge import JUDGE_CONCURRENCY, JUDGE_MODEL, judge_query
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
) -> tuple[ParsedIntentSummary, list[ProductSummary], str]:
    """Run the real recommendation pipeline for one query."""
    async with session_factory() as db:
        result = await recommend(db, test_query.query, available_online=False)

    intent = ParsedIntentSummary(
        categories=result.intent.categories,
        min_price=result.intent.min_price,
        max_price=result.intent.max_price,
        country=result.intent.country,
        available_online=False,
        semantic_query=result.intent.semantic_query,
    )
    products = [
        ProductSummary(
            sku=item.product.sku,
            name=item.product.name,
            category=item.product.category,
            country=item.product.country,
            price=item.product.price,
            producer=item.product.producer,
            grape=item.product.grape,
            region=item.product.region,
            taste_tag=item.product.taste_tag,
            rating=item.product.rating,
            review_count=item.product.review_count,
            online_availability=item.product.online_availability,
            reason=item.reason,
        )
        for item in result.products
    ]
    return intent, products, result.summary


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
    *,
    judge_runs: int = 1,
    judge_temperature: float = 0.0,
) -> EvalReport:
    """Run the full eval: pipeline -> judge -> report."""
    session_factory = create_session_factory(database_url)
    judge_client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    # Phase 1: Run pipeline sequentially (each hits Haiku + OpenAI + DB)
    collected: list[
        tuple[TestQuery, ParsedIntentSummary, list[ProductSummary], str, str | None]
    ] = []

    for i, test_query in enumerate(queries, 1):
        logger.info("[{}/{}] {}", i, len(queries), test_query.query)
        try:
            intent, products, summary = await _run_single(session_factory, test_query)
            logger.info(
                "  -> {} products | intent: {} {} {}",
                len(products),
                intent.categories,
                f"${intent.max_price}" if intent.max_price else "",
                intent.country or "",
            )
            collected.append((test_query, intent, products, summary, None))
        except Exception as exc:
            logger.opt(exception=exc).error("  Pipeline failed: {}", exc)
            collected.append((test_query, ParsedIntentSummary(), [], "", str(exc)))

    # Phase 2: Judge in parallel (Sonnet calls are independent)
    logger.info("Judging {} results with {}...", len(collected), JUDGE_MODEL)
    judge_tasks = []
    error_scores: dict[int, QueryScore] = {}
    semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)

    summaries: dict[int, str] = {}
    for test_query, intent, products, summary, error in collected:
        summaries[test_query.id] = summary
        if error:
            error_scores[test_query.id] = _make_error_score(test_query, dimensions, error)
        else:
            judge_tasks.append(
                judge_query(
                    judge_client,
                    test_query,
                    intent,
                    products,
                    dimensions,
                    judge_runs=judge_runs,
                    judge_temperature=judge_temperature,
                    semaphore=semaphore,
                )
            )

    judged = await asyncio.gather(*judge_tasks) if judge_tasks else []

    # Merge judged + error scores in original order
    judged_iter = iter(judged)
    query_scores: list[QueryScore] = []
    for test_query, *_ in collected:
        if test_query.id in error_scores:
            qs = error_scores[test_query.id]
        else:
            qs = next(judged_iter)
        qs.summary = summaries.get(test_query.id, "")
        query_scores.append(qs)

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

    # Phase 4: Tag-stratified averages (weighted avg per tag)
    tag_averages: dict[str, float] = {}
    tag_scores: dict[str, list[float]] = {}
    for qs, tq in zip(query_scores, queries):
        qs_weighted = (
            sum(qs.scores[d.name].score * d.weight for d in dimensions if d.name in qs.scores)
            / total_weight
            if total_weight > 0
            else 0.0
        )
        for tag in tq.tags:
            tag_scores.setdefault(tag, []).append(qs_weighted)
    for tag, scores in sorted(tag_scores.items()):
        tag_averages[tag] = round(sum(scores) / len(scores), 2)

    return EvalReport(
        judge_model=JUDGE_MODEL,
        judge_runs=judge_runs,
        judge_temperature=judge_temperature,
        rubric=dimensions,
        total_queries=len(queries),
        query_scores=query_scores,
        averages=averages,
        tag_averages=tag_averages,
        weighted_average=round(weighted_avg, 2),
    )

import argparse
import asyncio
import sys

from core.config.settings import settings
from loguru import logger

from backend.config import backend_settings

from .report import print_report, save_report
from .runner import run_eval
from .schemas import TestQuery, load_queries, load_rubric


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG recommendation pipeline evaluation")
    parser.add_argument(
        "--query",
        help="Run a single query by ID (integer) or text (string match)",
    )
    parser.add_argument(
        "--split",
        choices=["train", "holdout", "all"],
        default="train",
        help="Which query split to run (default: train)",
    )
    parser.add_argument(
        "--judge-runs",
        type=int,
        default=1,
        help="Number of judge runs to average (default: 1)",
    )
    parser.add_argument(
        "--judge-temp",
        type=float,
        default=0.0,
        help="Judge temperature (default: 0.0 for deterministic)",
    )
    return parser.parse_args()


def _filter_queries(queries: list[TestQuery], query_filter: str | None) -> list[TestQuery]:
    if query_filter is None:
        return queries

    # Try integer ID first
    try:
        query_id = int(query_filter)
        matching = [q for q in queries if q.id == query_id]
        if matching:
            return matching
    except ValueError:
        pass

    # Fall back to text substring match
    matching = [q for q in queries if query_filter.lower() in q.query.lower()]
    if matching:
        return matching

    # No match — run as ad-hoc query
    return [TestQuery(id=0, query=query_filter, tags=["ad-hoc"])]


async def main() -> int:
    args = _parse_args()

    if not backend_settings.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set — cannot run eval")
        return 1
    if not backend_settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set — cannot run eval")
        return 1

    queries = load_queries()
    queries = _filter_queries(queries, args.query)

    # Apply split filter (skip when --query targets a specific query)
    if args.query is None and args.split != "all":
        queries = [q for q in queries if q.split == args.split]

    dimensions = load_rubric()

    logger.info(
        "Running eval: {} queries ({} split), {} dimensions, {} judge run(s) @ temp={}",
        len(queries),
        args.split,
        len(dimensions),
        args.judge_runs,
        args.judge_temp,
    )

    report = await run_eval(
        database_url=settings.database_url,
        anthropic_api_key=backend_settings.ANTHROPIC_API_KEY,
        queries=queries,
        dimensions=dimensions,
        judge_runs=args.judge_runs,
        judge_temperature=args.judge_temp,
    )

    print_report(report)
    save_report(report)

    if report.weighted_average < 3.0:
        logger.warning(
            "Weighted average {:.2f} is below threshold (3.0)",
            report.weighted_average,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

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
    parser.add_argument(
        "--pipeline-runs",
        type=int,
        default=1,
        help="Repeat the full pipeline N times and report mean ± std (default: 1)",
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

    pipeline_runs = args.pipeline_runs
    run_kwargs = dict(
        database_url=settings.database_url,
        anthropic_api_key=backend_settings.ANTHROPIC_API_KEY,
        queries=queries,
        dimensions=dimensions,
        judge_runs=args.judge_runs,
        judge_temperature=args.judge_temp,
    )

    if pipeline_runs == 1:
        report = await run_eval(**run_kwargs)
        print_report(report)
        save_report(report)
        final_score = report.weighted_average
    else:
        scores: list[float] = []
        for i in range(pipeline_runs):
            logger.info("Pipeline run {}/{}", i + 1, pipeline_runs)
            report = await run_eval(**run_kwargs)
            save_report(report)
            scores.append(report.weighted_average)
            logger.info("  -> weighted avg: {:.2f}", report.weighted_average)

        # Print full scorecard for the last run + aggregate summary
        print_report(report)
        avg = sum(scores) / len(scores)
        std = (sum((s - avg) ** 2 for s in scores) / len(scores)) ** 0.5
        runs_str = ", ".join(f"{s:.2f}" for s in scores)
        print(f"\n  PIPELINE RUNS ({pipeline_runs}x): [{runs_str}]")
        print(f"  Mean: {avg:.2f}  Std: {std:.2f}\n")
        final_score = avg

    if final_score < 3.0:
        logger.warning("Weighted average {:.2f} is below threshold (3.0)", final_score)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

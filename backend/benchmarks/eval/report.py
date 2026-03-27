import json
from pathlib import Path

from loguru import logger

from .schemas import EvalReport, to_serializable

RESULTS_DIR = Path(__file__).parent / "results"


def _load_previous_report() -> EvalReport | None:
    """Load the most recent eval result for diff comparison."""
    results = sorted(RESULTS_DIR.glob("eval_*.json"))
    if not results:
        return None
    try:
        raw = json.loads(results[-1].read_text())
        return EvalReport(**raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _delta_str(current: float, previous: float | None) -> str:
    if previous is None:
        return ""
    diff = current - previous
    sign = "+" if diff >= 0 else ""
    return f" ({sign}{diff:.1f})"


def print_report(report: EvalReport) -> None:
    """Print a formatted scorecard to stdout."""
    previous = _load_previous_report()
    prev_avgs = previous.averages if previous else {}

    print("\n" + "=" * 70)
    print("  RAG EVAL SCORECARD")
    print("=" * 70)
    print(f"  Judge: {report.judge_model}")
    print(f"  Queries: {report.total_queries}")
    print()

    # Per-query table
    dim_names = [d.name for d in report.rubric]
    header = f"  {'ID':>3}  {'Query':<40}  " + "  ".join(f"{d:>10}" for d in dim_names)
    print(header)
    print("  " + "-" * (len(header) - 2))

    for qs in report.query_scores:
        scores_str = "  ".join(
            f"{qs.scores[d].score:>10}" if d in qs.scores else f"{'—':>10}" for d in dim_names
        )
        query_display = qs.query[:40]
        error_marker = " ✗" if qs.error else ""
        print(f"  {qs.query_id:>3}  {query_display:<40}  {scores_str}{error_marker}")

    # Averages
    print("  " + "-" * (len(header) - 2))
    for d in dim_names:
        avg = report.averages.get(d, 0)
        delta = _delta_str(avg, prev_avgs.get(d))
        print(f"  {d}: {avg:.1f}{delta}")
    print()

    prev_weighted = previous.weighted_average if previous else None
    weighted_delta = _delta_str(report.weighted_average, prev_weighted)
    print(f"  Weighted average: {report.weighted_average:.2f}{weighted_delta}")

    # Tag-stratified averages
    if report.tag_averages:
        prev_tag_avgs = previous.tag_averages if previous else {}
        print()
        print("  BY TAG:")
        for tag, avg in sorted(report.tag_averages.items(), key=lambda x: x[1]):
            delta = _delta_str(avg, prev_tag_avgs.get(tag))
            print(f"    {tag:<20} {avg:.2f}{delta}")

    print("=" * 70)

    # Low scores detail
    low_scores = [
        qs
        for qs in report.query_scores
        if any(qs.scores[d].score <= 2 for d in dim_names if d in qs.scores)
    ]
    if low_scores:
        print("\n  LOW SCORES (≤2):")
        for qs in low_scores:
            for d in dim_names:
                if d in qs.scores and qs.scores[d].score <= 2:
                    s = qs.scores[d]
                    print(f"    Q{qs.query_id} [{d}] = {s.score}: {s.justification}")
        print()


def save_report(report: EvalReport) -> Path:
    """Save eval report as JSON. Returns the file path."""
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = report.timestamp.replace(":", "-")
    path = RESULTS_DIR / f"eval_{timestamp}.json"

    # Summary fields first for readability — bulky query_scores last
    data = report.model_dump()
    ordered = {
        "timestamp": data["timestamp"],
        "judge_model": data["judge_model"],
        "judge_runs": data["judge_runs"],
        "judge_temperature": data["judge_temperature"],
        "weighted_average": data["weighted_average"],
        "averages": data["averages"],
        "tag_averages": data["tag_averages"],
        "total_queries": data["total_queries"],
        "rubric": data["rubric"],
        "query_scores": data["query_scores"],
    }

    path.write_text(
        json.dumps(
            ordered,
            indent=2,
            default=to_serializable,
            ensure_ascii=False,
        )
    )
    logger.info("Results saved to {}", path)
    return path

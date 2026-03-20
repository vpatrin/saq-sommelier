from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from prometheus_client import Counter, Histogram

if TYPE_CHECKING:
    import anthropic.types


def observe_token_usage(service: str, response: anthropic.types.Message) -> None:
    usage = getattr(response, "usage", None)
    if usage and isinstance(getattr(usage, "input_tokens", None), int):
        llm_tokens.labels(service=service, direction="in").inc(usage.input_tokens)
        llm_tokens.labels(service=service, direction="out").inc(usage.output_tokens)
    else:
        logger.warning("Missing token usage in Claude response for service={}", service)


# --- Recommendation pipeline ---

recommendation_duration = Histogram(
    "coupette_recommendation_duration_seconds",
    "Duration of each recommendation pipeline stage",
    ["stage"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

recommendation_candidates = Histogram(
    "coupette_recommendation_candidates",
    "Number of candidate products returned by vector search before reranking",
    buckets=(1, 5, 10, 25, 50, 100, 250),
)

recommendation_pipeline_errors = Counter(
    "coupette_recommendation_pipeline_errors_total",
    "Unhandled errors in the recommendation pipeline",
)

# --- Intent routing ---

intent_classifications = Counter(
    "coupette_intent_classifications_total",
    "How user queries are routed by intent type",
    ["intent_type"],
)

# --- LLM API calls (all services) ---

llm_tokens = Counter(
    "coupette_llm_tokens_total",
    "Claude API tokens across all services",
    ["service", "direction"],
)

llm_call_duration = Histogram(
    "coupette_llm_call_duration_seconds",
    "Raw Claude API call latency by service",
    ["service"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

llm_errors = Counter(
    "coupette_llm_errors_total",
    "Claude API failures by service",
    ["service"],
)

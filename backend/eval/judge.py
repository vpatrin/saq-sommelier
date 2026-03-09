import asyncio
import json
import re

import anthropic
from loguru import logger

from .schemas import (
    DimensionScore,
    ParsedIntentSummary,
    ProductSummary,
    QueryScore,
    RubricDimension,
    TestQuery,
    to_serializable,
)

JUDGE_MODEL = "claude-sonnet-4-20250514"
JUDGE_MAX_TOKENS = 1024
JUDGE_CONCURRENCY = 5

_semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)


def _build_rubric_text(dimensions: list[RubricDimension]) -> str:
    lines: list[str] = []
    for d in dimensions:
        lines.append(f"### {d.name} (weight: {d.weight})")
        lines.append(d.description)
        lines.append("")
    return "\n".join(lines)


def _build_output_example(dim_names: list[str]) -> str:
    template = '  "{}": {{"score": <1-5>, "justification": "<brief reason>"}},'
    return "\n".join(template.format(name) for name in dim_names)


def _build_system_prompt(dimensions: list[RubricDimension]) -> str:
    rubric_text = _build_rubric_text(dimensions)
    dim_names = [d.name for d in dimensions]

    return f"""\
You are an expert wine sommelier and search quality evaluator.

You will be given:
1. A user's wine query
2. The structured intent extracted by the system (for context only)
3. The list of wines returned by the recommendation engine
4. Expected signals (what the query should ideally match)

Score the results on each dimension using a 1-5 scale.
Provide a brief justification (1-2 sentences) for each score.

## Scoring rubric

{rubric_text}

## Output format

Return ONLY a JSON object with this exact structure, no markdown fences:
{{
{_build_output_example(dim_names)}
}}"""


def _build_user_message(
    test_query: TestQuery,
    intent: ParsedIntentSummary,
    products: list[ProductSummary],
) -> str:
    sections: list[str] = []

    sections.append(f"## User query\n{test_query.query}")

    sections.append(f"## Parsed intent (debug)\n{intent.model_dump_json(indent=2)}")

    if test_query.expected_categories:
        sections.append(f"## Expected categories\n{test_query.expected_categories}")
    if test_query.expected_country:
        sections.append(f"## Expected country\n{test_query.expected_country}")
    if test_query.expected_price_max:
        sections.append(f"## Expected max price\n${test_query.expected_price_max}")
    if test_query.notes:
        sections.append(f"## Notes\n{test_query.notes}")

    if not products:
        sections.append("## Results\nNo products returned.")
    else:
        product_lines = []
        for p in products:
            product_lines.append(
                json.dumps(
                    p.model_dump(),
                    default=to_serializable,
                    ensure_ascii=False,
                )
            )
        sections.append(f"## Results ({len(products)} products)\n" + "\n".join(product_lines))

    return "\n\n".join(sections)


def _parse_judge_response(
    text: str, dimensions: list[RubricDimension]
) -> dict[str, DimensionScore]:
    # Strip markdown fences if Sonnet wraps the JSON
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse judge JSON, returning score 1 for all dimensions")
        return {
            d.name: DimensionScore(score=1, justification="Judge response was not valid JSON")
            for d in dimensions
        }

    scores: dict[str, DimensionScore] = {}
    for d in dimensions:
        if d.name in raw:
            scores[d.name] = DimensionScore(**raw[d.name])
        else:
            scores[d.name] = DimensionScore(score=1, justification=f"Dimension '{d.name}' missing")
    return scores


async def _single_judge_call(
    client: anthropic.AsyncAnthropic,
    system_prompt: str,
    user_message: str,
    dimensions: list[RubricDimension],
    temperature: float,
) -> dict[str, DimensionScore]:
    """Run one judge call and return parsed scores."""
    response = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return _parse_judge_response(response.content[0].text, dimensions)


def _average_scores(
    runs: list[dict[str, DimensionScore]],
    dimensions: list[RubricDimension],
) -> dict[str, DimensionScore]:
    """Average scores across runs, keeping justification closest to mean."""
    result: dict[str, DimensionScore] = {}
    for d in dimensions:
        dim_scores = [r[d.name] for r in runs]
        mean = sum(s.score for s in dim_scores) / len(dim_scores)
        # Pick the justification from the run whose score is closest to the mean
        closest = min(dim_scores, key=lambda s: abs(s.score - mean))
        result[d.name] = DimensionScore(
            score=round(mean),
            justification=closest.justification,
        )
    return result


async def judge_query(
    client: anthropic.AsyncAnthropic,
    test_query: TestQuery,
    intent: ParsedIntentSummary,
    products: list[ProductSummary],
    dimensions: list[RubricDimension],
    *,
    judge_runs: int = 1,
    judge_temperature: float = 0.0,
) -> QueryScore:
    """Score a single query's results using Claude Sonnet as judge."""
    system_prompt = _build_system_prompt(dimensions)
    user_message = _build_user_message(test_query, intent, products)

    async with _semaphore:
        try:
            runs: list[dict[str, DimensionScore]] = []
            for _ in range(judge_runs):
                run_scores = await _single_judge_call(
                    client,
                    system_prompt,
                    user_message,
                    dimensions,
                    judge_temperature,
                )
                runs.append(run_scores)
            scores = _average_scores(runs, dimensions) if len(runs) > 1 else runs[0]
        except anthropic.APIError as exc:
            logger.opt(exception=exc).warning("Judge API call failed for query {}", test_query.id)
            scores = {
                d.name: DimensionScore(score=1, justification="Judge API call failed")
                for d in dimensions
            }

    return QueryScore(
        query_id=test_query.id,
        query=test_query.query,
        scores=scores,
        parsed_intent=intent,
        products=products,
    )

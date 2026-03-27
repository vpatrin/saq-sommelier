# Benchmarks

Trend analysis and comparisons across load tests and AI evaluations. Raw data lives closer to the code:

- **Load tests** — [backend/benchmarks/load/](../backend/benchmarks/load/) (k6 scripts + results)
- **AI evals** — [backend/benchmarks/eval/](../backend/benchmarks/eval/) (eval runner + results)

This directory holds synthesized reports: trends over time, before/after comparisons, and cross-cutting analysis.

## Reports

| Report | Description |
| ------ | ----------- |
| *(none yet)* | Run the first baseline and add a summary here |

## Report format

Each report is a markdown file with:

1. **Context** — what changed, what tier we're testing
2. **Methodology** — VUs, duration, which scripts
3. **Results** — tables comparing key metrics (p50, p95, p99, error rate)
4. **Findings** — what broke, what held, what to do next
5. **Raw data references** — links to the JSON files in `backend/benchmarks/load/` or `backend/benchmarks/eval/`

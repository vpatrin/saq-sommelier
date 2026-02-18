# Observability Roadmap

Part of the [project roadmap](../ROADMAP.md). From PostgreSQL logging to full Grafana + Prometheus + Loki stack.

## Phase 1 — Foundation (~1 day)

- [x] App logs → stdout via loguru (#85)
- [x] PYTHONUNBUFFERED in all Dockerfiles (#3, #4)
- [ ] API request logging middleware → `api_request_logs` table (method, path, status, latency, user_id)
- [ ] LLM call logging wrapper → `llm_logs` table (function, model, tokens, cost, latency, success)
- [ ] RAG trace logging → `rag_traces` table (query, filters, candidates, recommendation, config version)
- [ ] User feedback → `recommendation_feedback` table (user_id, trace_id, rating)
- [ ] Retention policy — API logs 30 days, LLM/traces 90 days, feedback forever

## Phase 2 — Dashboards (~1 day)

- [ ] Grafana container + Caddy route (monitoring.victorpatrin.dev)
- [ ] Dashboard: LLM cost & performance — daily spend, latency by function, token usage, cost per user
- [ ] Dashboard: API health — req/min, response time distribution, error rate, slowest queries
- [ ] Dashboard: Recommendation quality — satisfaction rate, thumbs down queries, popular searches
- [ ] Dashboard: Scraper health — products per run, new/updated/delisted, duration, errors

## Phase 3 — Structured Logging (~half day)

- [ ] JSON log formatter for all services
- [ ] Consistent fields: timestamp, level, service, message, structured extras
- [ ] Loki-ready without Loki (queryable when you add it later)

## Phase 4 — Alerting (~half day)

Alerting rules and ops digest owned by [SRE](sre.md). This phase wires the observability data into those alerts.

- [ ] Telegram alert system with severity levels and cooldowns
- [ ] Alert rules: error rate, latency, data staleness, satisfaction, cost anomaly, disk, memory
- [ ] Weekly ops digest — automated Monday summary via Telegram

## Phase 5 — Prometheus Metrics (VPS upgrade, ~1 day)

- [ ] Prometheus container + scrape config
- [ ] Application metrics — counters (requests, LLM calls, recommendations), histograms (latency), gauges (products, vectors, daily cost)
- [ ] Real-time Grafana dashboards from Prometheus

## Phase 6 — Loki Log Aggregation (VPS upgrade, ~1 day)

- [ ] Loki + Promtail containers
- [ ] Centralized log search across all services in Grafana
- [ ] Correlation: slow request → which LLM call caused it

## Phase 7 — Distributed Tracing (optional, portfolio)

- [ ] OpenTelemetry instrumentation + Tempo/Jaeger
- [ ] Per-request trace through entire pipeline (bot → API → Claude → ChromaDB → response)

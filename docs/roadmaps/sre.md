# SRE Roadmap

Part of the [project roadmap](../ROADMAP.md). SLOs, alerting, incident management, reliability testing, capacity planning.

## Phase 1 — Define SLOs (~half day)

- [ ] docs/SLOs.md — SLIs and SLOs for API (p95 < 500ms, 99% uptime, < 1% 5xx), RAG pipeline (p95 < 5s, > 70% satisfaction, 0% hallucinations), scraper (100% weekly completion, data < 8 days old), bot (ack < 2s)
- [ ] SLO monitoring queries for Grafana — availability, latency, satisfaction, data freshness

## Phase 2 — Monitoring & Alerting (~1 day)

- [ ] Health check endpoints — `/health` (quick) + `/health/detailed` (Postgres, ChromaDB, Claude API, data freshness)
- [ ] Telegram alert manager — severity levels (info/warning/error/critical), 15-minute cooldown per alert title
- [ ] Alert rules — error rate > 5%, p95 > 500ms, data > 8 days stale, satisfaction < 70%, LLM cost > $1/day, disk > 85%, memory > 85%
- [ ] Scheduled checks every 5 minutes via APScheduler

## Phase 3 — Incident Management (~half day)

- [ ] docs/RUNBOOK.md — diagnostics for every failure mode (service down, bot unresponsive, recommendations broken, scraper failed, ChromaDB down, Postgres issues, high memory)
- [ ] docs/INCIDENTS.md — postmortem template (date, duration, severity, impact, root cause, timeline, action items)

## Phase 4 — Reliability Testing (~1 day)

- [ ] Load testing with Locust — API endpoints + /recommend, record baseline capacity
- [ ] docs/CAPACITY.md — load test results table, bottleneck analysis
- [ ] Chaos testing (manual, documented) — kill each container, fill disk, OOM simulation, network partition, Claude API down
- [ ] Graceful degradation — fallback chain: full pipeline → SQL + Claude → SQL only → service unavailable

## Phase 5 — Toil Reduction (~half day)

- [ ] docs/TOIL.md — identify manual tasks and automation plan
- [ ] Weekly ops digest via Telegram — products, LLM cost, p95 latency, satisfaction, disk, backup status, SLO compliance

## Phase 6 — Capacity Planning (~half day)

- [ ] Resource tracking — disk, memory, swap, DB size, growth rate
- [ ] docs/SCALING.md — upgrade triggers, scaling path (CX22 → CX32 → CX42 → Kubernetes)

## Phase 7 — On-Call Documentation (~half day, portfolio)

- [ ] docs/ON_CALL.md — escalation path, priority levels (P1-P4), response times, handoff template

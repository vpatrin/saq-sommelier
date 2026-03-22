# Scaling Log

Living document: part changelog, part roadmap. Each tier starts as a plan, then fills in with what actually happened — decisions, measurements, and results. The story of how Coupette scales from 1 user to 10,000+.

**Done** entries record what was implemented, when, and why. **Planned** entries are what's next. Each tier has k6 benchmarks — before and after.

Design principle: **measure first, optimize the box, then scale the infrastructure.**

### Scaling philosophy

1. **Measure** — instrument everything, establish baselines, find where time goes
2. **Optimize** — pure config and code changes on the same hardware. No new services, no VPS upgrade
3. **Scale up** — add services (Redis, PgBouncer) and bump the VPS when the box is fully squeezed
4. **Scale out** — k3s, horizontal replicas, multi-node. Only when vertical hits a wall

---

## Current Baseline

| Component | Configuration | Notes |
|-----------|--------------|-------|
| VPS | Hetzner CX22 — 4GB RAM, 40GB SSD, 2GB swap | Shared with Uptime Kuma, Umami, observability stack (~600MB for Alloy/Loki/Prometheus) |
| Database | Shared Postgres 16 + pgvector, `max_connections=100` | SQLAlchemy async, backend pool: size=10, overflow=10, timeout=5s |
| Backend | Single uvicorn async worker, 512MB mem limit | Stateless, horizontally scalable by design |
| Bot | 256MB mem limit, long polling | Stock alerts triggered by scraper `--availability-check`, not bot polling |
| Scraper | 512MB mem limit, weekly + 6h availability check | 2s rate limit between SAQ requests |
| Vector store | ~14k vectors, exact scan (no index) | OpenAI `text-embedding-3-large` |
| LLM | Claude Haiku (intent + curation + sommelier) | OpenAI embeddings for query + product vectors |
| Monthly infra cost | ~€7 (CX22 VPS share) | Excludes domain, LLM API |

---

## Tier 1: Measure — Baseline & Observability

**Objective:** Instrument everything, establish baselines, build the testing framework, fix the obvious. SRE stack (Grafana/Prometheus/Alloy in infra repo) + k6 load testing + first perf fix.

### Done

#### 2026-03-21 — Prometheus metrics + pipeline instrumentation (#497)

**Context:** No runtime observability — can't scale what you can't measure. Needed baselines before making any performance decisions.
**Action:** Added `prometheus-fastapi-instrumentator` with custom histograms on the recommendation pipeline (intent parsing, curation, embedding, LLM round-trip). Each pipeline stage reports its own duration.
**Result:** `/metrics` endpoint live. Grafana dashboards show per-stage latency breakdown. Baseline: search p95 ~sub-500ms, recommendation pipeline 5-6s (dominated by embedding + LLM calls).

#### 2026-03-21 — Facets query parallelization (#509)

**Context:** Facets endpoint ran 5 sequential DB queries on a single session — p95 ~450ms, approaching the 500ms threshold. Simple code change with high impact — the 5 queries are independent, so parallelism is free.
**Action:** Refactored to `asyncio.gather` with independent sessions per query (a single `AsyncSession` can't run concurrent queries on the same connection). Added `session_factory` dependency alongside the existing `db` session.
**Result:** Facets p95 dropped significantly. Connection pool pressure shifted from 1 long-held connection to 5 short-lived ones (better pool utilization).

#### 2026-03-21 — Connection pool tuning (#509)

**Context:** Backend engine used SQLAlchemy defaults — not tuned for the new parallel workload. With facets now opening 5 connections per request, needed explicit configuration. `pool_pre_ping` catches stale connections from Postgres restarts.
**Action:** Configured `pool_size=10`, `max_overflow=10`, `pool_timeout=5s`, `pool_pre_ping=True` on the async engine. Settings exposed via env vars (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`).
**Result:** Pool sized for worst case: facets (5 connections) + concurrent search/chat requests. Total max = `pool_size + max_overflow` = 20 connections from backend alone — well within Postgres `max_connections=100`.

#### 2026-03-21 — k6 load testing framework (#509)

**Context:** No way to validate scaling changes or find the break point before real users hit it. Without load testing, scaling decisions are guesswork.
**Action:** Built k6 test scripts for all major endpoints (search, chat, watches, stores, mixed workload) with a tier-1 baseline runner script. Config externalized for different tiers.
**Result:** Framework ready at `backend/benchmarks/load/`. Baseline run pending — will establish the numbers that trigger Tier 2 work.

### What to monitor

- API p95 latency (baseline: sub-500ms for search, 5-6s for recommendations — dominated by embedding + LLM calls)
- DB connection count (backend pool: size=10, overflow=10)
- VPS memory usage (target: keep ~1GB free — observability stack claims ~600MB)
- Claude API monthly spend

**Cost:** ~$10/mo total (VPS share + LLM APIs)

### Signals to advance to Tier 2

- API p95 consistently > 500ms on search/filter endpoints
- DB connection pool saturation warnings in logs
- VPS available memory regularly < 500MB (swap pressure)

---

## Tier 2: Optimize — Squeeze the CX22

**Objective:** Maximum performance from the same hardware. Pure config, code, and query optimization — no new services, no VPS upgrade.

### Done

*(nothing yet)*

### Planned

#### Missing indexes

**Context:** No slow query analysis done yet. As query volume grows, unindexed columns become the bottleneck. Likely candidates: `products(category, country)` for filtered search, `watches` partial index for availability joins, `chat_messages(session_id, created_at)` for conversation loading.
**Action:** Enable `pg_stat_statements`, analyze actual slow queries, add targeted indexes where data shows > 100ms queries.

#### pgvector HNSW index

**Context:** Exact scan is fine at 14k vectors. At ~50k+ vectors or similarity search p95 > 200ms, exact scan becomes the bottleneck.
**Action:** HNSW index on `products.embedding` — no retraining needed when rows change (unlike IVFFlat), better recall at comparable speed.

#### API rate limiting

**Context:** Claude API costs scale linearly with chat requests — a single abusive user could burn the monthly budget. Need cost protection before opening to more users.
**Action:** Per-user rate limits on `/api/chat`. Start simple: N requests/minute. Options: `slowapi` (app-level) or Caddy rate limiting (infra-level, no code change).

#### Embedding cache

**Context:** The embedding call adds ~1.5-2s to every recommendation pipeline run. Same query text always produces the same vector — latency wasted on repeat queries.
**Action:** In-memory dict with TTL. Cache OpenAI embedding API calls by normalized query string. No Redis dependency yet — keep it in-process.

#### Separate metrics port

**Context:** `/metrics` is publicly reachable via Caddy's `/api/*` route, and Prometheus scraping adds noise to request metrics at scale.
**Action:** Move metrics to a dedicated internal port (e.g. `:9090`). Either a second uvicorn app or `prometheus-fastapi-instrumentator`'s built-in separate ASGI app.

#### Bot webhook migration

**Context:** Long polling adds constant backend load regardless of activity. Webhooks are a config change, not new infrastructure — Caddy already provides the HTTPS endpoint.
**Action:** Replace long polling with Telegram webhooks. Notification delivery shifts from polling to event-driven push.

### k6 targets

| Scenario | Before (Tier 1 baseline) | Target |
|----------|--------------------------|--------|
| Search p95 | TBD | < 200ms |
| Facets p95 | ~450ms → parallelized | < 150ms |
| Recommendation p95 | 5-6s (LLM-dominated) | < 4s (embed cache) |
| Mixed 50 VU sustained | TBD | No errors, p95 < 500ms (excl. chat) |

### Signals to advance to Tier 3

- Same queries repeated by different users (cache hit ratio would save > 50% of DB reads)
- Connection pool saturation despite tuning
- Single worker CPU > 70% sustained
- LLM cost growing faster than acceptable (> $20/mo on Claude)

---

## Tier 3: Scale Up — Add Services + CX33

**Objective:** Introduce caching infrastructure and bump the VPS. PgBouncer, Redis, backend replicas, VPA right-sizing. Still single-node.

### Done

*(nothing yet)*

### Planned

#### VPS upgrade to CX33

**Context:** CX22 (4GB) is shared with observability stack (~600MB), Uptime Kuma, Umami. After Tier 2 optimizations, the bottleneck shifts from code to memory. CX33 doubles RAM (8GB) for ~€8/mo more.
**Action:** Hetzner upgrade CX22 → CX33. No migration needed — Hetzner does live resize.

#### PgBouncer

**Context:** Multiple services (backend replicas, bot, scraper) each maintain connection pools against shared Postgres. With replicas, real connection count approaches `max_connections=100`.
**Action:** Connection pooler in front of shared Postgres, transaction pooling mode. App connection strings point to PgBouncer instead of Postgres directly.

#### Redis cache layer

**Context:** Same queries hit Postgres repeatedly — product search, facets, store data. Cache-aside with TTL-based invalidation (15min–24h depending on data freshness) eliminates redundant DB reads.
**Action:** Redis container + thin cache-aside pattern in repository layer. Check Redis first, fall through to Postgres, populate on miss. Invalidate on scraper runs.

#### LLM response cache

**Context:** Claude API costs scale with users, but many queries are universal ("wines under $20 for pasta"). Short TTL (1-4h) caches these without stale personalization.
**Action:** Cache recommendation responses by `hash(normalized_query + intent + filter_params)`. Move embedding cache from in-memory to Redis (shared across replicas). Exclude user-specific context from cache key (taste profile makes this per-user in Phase 12).

#### Multiple backend replicas

**Context:** Single uvicorn worker — one blocked request reduces throughput for everyone. With CX33's headroom and PgBouncer managing connections, replicas become viable.
**Action:** Container replicas behind Caddy upstream with health checks. Docker Compose `deploy.replicas`. VPA (recommend mode first) to right-size resource requests per replica.

#### Read replica

**Context:** Write contention or read p95 > 500ms despite indexes and caching — single Postgres can't serve both read-heavy search and write-heavy chat/watches.
**Action:** Postgres streaming replication. Route read-only queries (search, facets, product detail) to replica. Writes (watches, chat messages) stay on primary. Needs careful read-after-write consistency handling.

### k6 targets

| Scenario | Before (Tier 2) | Target |
|----------|-----------------|--------|
| Search p95 | < 200ms | < 100ms (Redis cache hits) |
| Facets p95 | < 150ms | < 50ms (Redis cache hits) |
| Recommendation p95 | < 4s | < 3s (LLM response cache hits: instant) |
| Mixed 200 VU sustained | TBD | No errors, p95 < 300ms (excl. chat) |

### Signals to advance to Tier 4

- Claude API costs > $50/mo despite response caching
- Recommendation p95 dominated by LLM round-trip (> 3s) for cache misses
- Request queue depth growing (more concurrent recommendations than replicas can handle)
- VPS CPU consistently > 80% during peak hours on CX33

---

## Tier 4: Scale Out — k3s & Horizontal

**Objective:** k3s migration, horizontal autoscaling, async processing. Multi-node when single-node CX33 hits its ceiling.

### Done

*(nothing yet)*

### Planned

#### Async task queue

**Context:** At scale, synchronous LLM calls block the request cycle — recommendation requests queue up behind each other. Need to decouple the request from the LLM round-trip.
**Action:** User sends message → backend returns task ID immediately → worker processes asynchronously → client receives SSE update. ARQ (Redis-backed, async-native) over Celery — lighter, fits solo dev context. Redis already in place from Tier 3.

#### SSE streaming

**Context:** Already spec'd as Phase 9 (#427). At this tier it's no longer optional — users won't tolerate synchronous 5-6s waits. First token in ~200ms vs waiting for the full pipeline.
**Action:** Backend SSE endpoint + frontend streaming renderer. Token-by-token LLM response rendering.

#### Response pre-computation

**Context:** Popular queries are predictable ("red wines under $20", "wines for BBQ"). Waiting for real-time LLM calls on universal queries wastes latency and money.
**Action:** Scheduled job batch-generates recommendations for popular query patterns during off-peak. Populates the LLM response cache proactively. Requires query analytics to identify which patterns are worth pre-computing.

#### HPA — horizontal pod autoscaling

**Context:** Manual replica management doesn't scale. Backend is stateless — autoscaling is straightforward with the right metrics.
**Action:** k3s Deployment with HPA scaling on custom Prometheus metrics (request queue depth, recommendation pipeline concurrency) rather than raw CPU — LLM-heavy workloads are I/O-bound, not CPU-bound. VPA continues right-sizing individual pods.

#### Multi-node k3s

**Context:** Single CX33 (8GB) ceiling reached. Multi-node gives fault tolerance + horizontal capacity.
**Action:** k3s cluster across 2-3 CX22s (~€21/mo) or CX33s. Better fault tolerance than one large VPS. Alternatively, vertical to CX42 (16GB, €15.90/mo) if ops simplicity matters more.

#### LLM provider redundancy

**Context:** Single provider dependency — Claude outage = total recommendation failure. At scale, downtime is unacceptable.
**Action:** Fallback chain: Claude Haiku → retry with backoff → degraded response (cached/pre-computed). Circuit breaker: if Claude p95 > 5s for 5 min, serve cached responses automatically.

#### CDN for frontend

**Context:** Not a capacity concern at earlier tiers (Hetzner bandwidth is unmetered), but with global distribution, edge caching reduces latency significantly.
**Action:** Cloudflare free tier in front of `coupette.club` — caches static SPA assets at the edge.

#### Database partitioning

**Context:** Products table is bounded (~14k, SAQ catalog). But user-generated data (chat_messages, recommendation_logs, tasting_notes) grows linearly — estimate ~1M chat messages/year at 10k users. Postgres handles 10M+ rows fine with proper indexing.
**Action:** Range partition on `created_at` only when query performance degrades despite indexes. Not a preemptive move.

### k6 targets

| Scenario | Before (Tier 3) | Target |
|----------|-----------------|--------|
| Search p95 | < 100ms | < 50ms (HPA + cache) |
| Recommendation p95 | < 3s | < 1s first token (SSE streaming) |
| Mixed 1000 VU sustained | TBD | No errors, auto-scales to demand |
| Cache hit ratio | TBD | > 70% on search, > 40% on recommendations |

---

## k3s Migration: Impact on Each Tier

k3s is an **enabler, not a prerequisite** — Tiers 1-2 don't need it at all. k3s makes Tier 3 easier and Tier 4 possible.

| Tier | Docker Compose Path | k3s Path |
|------|-------------------|----------|
| 2 (Optimize) | No infra changes — pure config/code | N/A |
| 3 (Scale Up) | `deploy.replicas` + manual Redis + PgBouncer | Deployments, Helm charts, VPA |
| 4 (Scale Out) | Hard to auto-scale, manual replica management | HPA, rolling deploys, multi-node cluster |

**When to migrate:** before or during Tier 3. Redis, replicas, and VPA are where Compose starts getting painful. But don't block scaling work on the migration.

---

## Decision Points Summary

| Action | Tier | Trigger Metric | Status |
| -------- | ------ | --------------- | ------ |
| Prometheus metrics | 1 Measure | — (foundational) | Done (#497) |
| Facets parallelization | 1 Measure | Facets p95 approaching 500ms | Done (#509) |
| Connection pool tuning | 1 Measure | Pool defaults unsuitable for parallel queries | Done (#509) |
| k6 load testing | 1 Measure | — (foundational) | Done (#509) |
| Missing indexes | 2 Optimize | Slow query log shows > 100ms queries | Planned |
| pgvector HNSW index | 2 Optimize | Vector count > 30k or similarity p95 > 200ms | Planned |
| API rate limiting | 2 Optimize | Any non-trivial user count (cost protection) | Planned |
| Embedding cache (in-memory) | 2 Optimize | Pipeline p95 dominated by embed step | Planned |
| Separate metrics port | 2 Optimize | `/metrics` publicly reachable or scraping noise | Planned |
| Bot webhooks | 2 Optimize | Polling load visible in backend metrics | Planned |
| VPS upgrade CX33 | 3 Scale Up | Memory pressure after Tier 2 optimizations | Planned |
| PgBouncer | 3 Scale Up | Connection count approaching max_connections | Planned |
| Redis cache | 3 Scale Up | Repeated query ratio > 50% | Planned |
| LLM response cache (Redis) | 3 Scale Up | Claude spend > $20/mo | Planned |
| Backend replicas | 3 Scale Up | Single worker CPU > 70% sustained | Planned |
| VPA (recommend mode) | 3 Scale Up | Resource requests don't match actual usage | Planned |
| Read replica | 3 Scale Up | Write contention or read p95 > 500ms | Planned |
| Async task queue | 4 Scale Out | Recommendation queue depth > 10 concurrent | Planned |
| SSE streaming | 4 Scale Out | Synchronous pipeline latency unacceptable | Planned |
| Response pre-computation | 4 Scale Out | Cache miss rate > 50% on popular queries | Planned |
| HPA | 4 Scale Out | Manual scaling becomes a weekly chore | Planned |
| Multi-node k3s | 4 Scale Out | CX33 ceiling reached | Planned |
| LLM fallback chain | 4 Scale Out | Claude error rate > 1% or p95 > 5s | Planned |
| CDN | 4 Scale Out | Global latency or bandwidth concerns | Planned |
| Table partitioning | 4 Scale Out | Query degradation despite indexes (10M+ rows) | Planned |

---

## Cost Projection Summary

| Tier | Users | Monthly Cost | Biggest Cost Driver |
|------|-------|-------------|-------------------|
| 1 Measure | 20 | ~$10 | VPS |
| 2 Optimize | 200 | ~$10 | Same hardware, no new costs |
| 3 Scale Up | 2,000 | ~$50-100 | CX33 + LLM API calls |
| 4 Scale Out | 10,000+ | ~$150-400 | LLM API calls + multi-node |

Tier 2 is the cheapest tier — pure optimization, no new infrastructure. LLM costs dominate from Tier 3 onward. Caching and pre-computation are the primary cost controls.

---

## Benchmarks

Each tier should be validated with load tests before and after changes. Tooling, scripts, and roadmap live in [ENGINEERING.md](ENGINEERING.md#benchmarks).

### Per-tier test plan

| Tier | VUs | Scenarios | What you're measuring |
| ---- | --- | --------- | --------------------- |
| 1 Measure | 1-5 | Search, chat, watches | Latency baselines, where time goes |
| 1→2 break | 10-50 ramp | Mixed workload | Find the CX22 break point |
| 2 Optimize | 50 sustained | Same scenarios | Prove pure config/code fixes worked |
| 2→3 break | 100-200 ramp | Heavy on chat | Find the single-node ceiling |
| 3 Scale Up | 200 sustained | Full workload | Validate CX33 + Redis + replicas |
| 3→4 break | 500-1000 ramp | Chat-heavy | Find the single-node CX33 ceiling |

### Considerations

- **LLM costs:** high-VU chat tests burn Claude credits. Use a mock LLM endpoint for infra stress testing, real LLM for latency profiling at low VU
- **Auth:** k6 scripts need valid JWTs — use a dedicated test user
- **Rate limiting:** if rate limits are in place (Tier 2+), either exempt the test user or measure the limiter behavior itself

---

## Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, scaling path summary table
- [ADR 0001: Modular Monolith](decisions/0001-modular-monolith.md) — why the architecture supports horizontal scaling
- [ADR 0005: RAG Pipeline](decisions/0005-rag-pipeline.md) — LLM and vector search performance characteristics
- [ENGINEERING.md](ENGINEERING.md#sre) — SRE backlog (SLOs, health endpoints)
- [Infra ROADMAP](https://github.com/vpatrin/infra/blob/main/docs/ROADMAP.md) — k3s migration, platform infrastructure

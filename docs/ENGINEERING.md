# Engineering

Discipline-level targets across testing, security, observability, platform engineering, SRE, environment segregation, and ML/MLOps.

Granular task breakdowns live in GitHub issues. This file tracks what's done and what's next at a strategy level.

---

## Testing

**Done:** Unit tests for scraper (products, stores, sitemap, robots), backend (endpoints, services, repositories), bot (handlers, filters, formatters, keyboards). Coverage thresholds enforced in CI (scraper ≥75%, backend ≥80%, bot ≥90%). Alignment tests verify dataclass ↔ model column sync.

**Next:**
- Add pytest markers (`unit/integration/ml/slow`) — prerequisite for running test subsets and separating fast CI from slow integration runs (#204)
- Product test factory (`make_red()`, `make_white()`, `make_wines(n)`) — eliminates repeated fixture setup and makes new tests faster to write
- Integration tests: seeded PostgreSQL fixture, repository layer (search, filter, pagination, upsert idempotency) — currently only SQLite mocks
- Contract tests: snapshot API response shapes so bot's assumptions are validated on every PR — catches breaking changes before deploy
- ML tests: embedding dimensions, retrieval quality, guardrail edge cases (Phase 6)

---

## Security

**Done:** Dependabot (pip + GitHub Actions weekly), Hadolint (Dockerfile linting in CI), pip-audit (vulnerability scanning in CI), gitleaks (secret detection in CI), CORS configuration (env-driven allowed origins), input validation (Pydantic, max lengths), Telegram user allowlist (`ALLOWED_USER_IDS` env var, #178), per-user rate limiting (#178).

**Next:**
- Infrastructure hardening: SSH key-only auth, UFW (allow 22/80/443 only), Fail2ban, unattended-upgrades — one-time VPS setup, done once and never touched again
- Docker secrets: move bot token + DB password from `.env` file to Docker secret files — eliminates plaintext credentials on disk
- `.env` audit: verify no secrets committed in git history (`git log -S 'password'`)
- API key auth: `X-API-Key` header on bot→backend calls — needed once the React dashboard exposes the API publicly
- `SECURITY.md`: responsible disclosure policy — one-page file, strong portfolio/interview signal

---

## Observability

**Done:** Structured logging via Loguru with service context (service name, log level, ISO timestamps). Scraper run summary emitted at exit (inserted/updated/errors/restocked/delisted/duration). Loguru `SUCCESS` level used for per-product success lines.

**Next:**
- Scraper failure alert: systemd `OnFailure=` unit sends Telegram DM on `EXIT_FAILURE` — currently silent failures with no visibility
- API request logging middleware → `api_request_logs` table (path, status, latency, user_id) — baseline for SLO tracking
- Structured JSON logging: consistent fields (timestamp, level, service, message) across all services — Loki/Grafana-ready without Loki
- Grafana: scraper health + API health dashboards — needs VPS CX32 upgrade for RAM headroom
- LLM cost tracking: token usage per request, daily budget cap alert (Phase 6)

---

## Platform Engineering

**Done:** Makefile (per-service and combined targets for install, dev, lint, format, test, coverage, audit, build, run). Docker Compose (dev profile for postgres, production for backend + bot). CI/CD (lint + test + audit per service, Hadolint, coverage enforcement, concurrency cancel-in-progress). Systemd timers for production scheduling. Scoped git hooks (pre-commit lints changed services, pre-push tests changed services + checks lock files + migration coverage).

**Next:**
- `docs/DEPLOYMENT.md` (#227): deploy flow, migration order, rollback procedure, initial VPS bootstrap — production is live but the process is only in your head
- `infra/scripts/backup-db.sh`: daily PostgreSQL dump + 7-day retention, systemd timer at 3am — no backups is the single biggest production risk right now
- CD pipeline: push to main → build image → push to GHCR → SSH deploy to VPS — currently manual and undocumented
- Image tagging: `:latest` for production, `:YYYYMMDD-HHMMSS` for rollback archive — enables one-command rollback
- `docker-compose.prod.yml`: explicit resource limits, restart policies, health checks, no debug ports — current compose mixes dev and prod concerns

---

## SRE

**Done:** Systemd timer with `Persistent=true` (runs on reboot if missed). Idempotent scraper (safe to re-run at any point). Named exit codes (`EXIT_SUCCESS`/`EXIT_PARTIAL`/`EXIT_FAILURE`) for monitoring. Bot runs 24/7 with PTB's built-in error handler.

**Next:**
- Telegram alert on scraper failure: systemd `OnFailure=` → Telegram DM — first SRE win, low effort, high value
- `/health/detailed` endpoint: Postgres reachability, data freshness (age of newest product), disk space — foundation for everything below
- Define SLOs: API p95 < 500ms, 99% uptime; scraper completes weekly, data < 8 days stale; bot ack < 2s
- `docs/RUNBOOK.md`: what to do when scraper fails, DB is full, bot goes offline, bad deploy — 1 page, prevents panic at 2am
- Graceful degradation chain for Phase 6: full RAG → SQL + Claude → SQL only → "service unavailable" message

---

## Environment Segregation

**Done:** Single `.env` pattern with env-specific defaults. Pydantic `BaseSettings` with fail-fast on missing required vars. `ENVIRONMENT` flag gates debug behavior. `DATABASE_ECHO` flag for SQL query logging in dev.

**Next:**
- `docker-compose.prod.yml`: production-specific compose with no hot-reload volumes, explicit restart policies, no debug ports
- Secrets injection: migrate bot token + DB credentials from `.env` file to Docker secrets or environment-injected at deploy time
- Staging environment: separate DB, separate `@SAQSommelierStagingBot` token — only needed when multi-person or when preview deploys matter

---

## ML / MLOps

**Not started.** See [ROADMAP.md](ROADMAP.md) Phase 6.

Key decisions already made:
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`) via ChromaDB (embedded, no separate service)
- **LLM:** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`, fast + cheap, ~$0.0001/query)
- **Pattern:** RAG over fine-tuning — catalog changes weekly, embeddings update incrementally

**Next:**
- Write `docs/specs/AI_RAG.md` (#228) before coding — lock in ChromaDB setup, retrieval strategy, guardrails, and prompt design first
- ChromaDB setup + `scraper/src/embed_sync.py` — post-scrape embedding pipeline for ~38k products
- Bilingual eval checkpoint: if FR/EN retrieval overlap < 50%, swap `all-MiniLM-L6-v2` → `multilingual-MiniLM`
- `backend/services/rag_service.py` + `guardrails.py` — Claude integration with hallucination prevention, versioned prompt config
- LLM call logging + user feedback loop (`👍👎` → `recommendation_feedback` table) — needed to measure quality
- HyDE, semantic caching, eval in CI — Phase 7, only after baseline eval data collected

# Environment Segregation Roadmap

Part of the [project roadmap](../ROADMAP.md). Four environments: local, test, staging, production. Same codebase, different config.

## Phase 1 — Configuration Foundation (~half day)

- [x] Pydantic BaseSettings for all services (#5)
- [x] CORS origins via BackendSettings (PR #80)
- [ ] Environment enum (local/test/staging/production), feature flags, derived properties
- [ ] .env.example (committed) + .env.test (committed, no secrets) + .env/.env.local/.env.staging/.env.production (gitignored)
- [ ] `core/config/guards.py` — `require_env()` decorator, `block_production()`, `warn_production()`

## Phase 2 — Local Dev Environment (~half day)

- [ ] docker-compose.dev.yml — hot reload via volumes, exposed ports for debugging, Swagger UI enabled
- [ ] Makefile targets — `dev`, `dev-build`, `dev-down`, `dev-reset`

## Phase 3 — Test Environment (~half day)

- [ ] docker-compose.test.yml — PostgreSQL + ChromaDB on tmpfs (RAM disk), different ports
- [ ] Mock fixtures — auto-mock Claude API and Telegram bot in all tests
- [ ] Safety net — `pytest_configure` refuses to run against production DB

## Phase 4 — Staging Environment (~1 day)

- [ ] Create @SAQSommelierStagingBot via @BotFather (separate token)
- [ ] docker-compose.staging.yml — separate DB, separate ChromaDB, smaller memory limits
- [ ] Caddy route — staging-wine.victorpatrin.dev (basic auth protected)
- [ ] Staging data seed script — 1000 product subset from production

## Phase 5 — Production Hardening (~1 day)

- [ ] docker-compose.prod.yml — see [Platform Phase 2](platform-engineering.md) for prod Docker baseline
- [ ] Environment-aware app startup — verify all services in production, skip in local
- [ ] Environment-aware CORS — different origins per environment
- [ ] Environment-aware logging — human-readable locally, JSON in staging/production

## Phase 6 — CI/CD Promotion Pipeline (~1 day)

- [ ] Image tagging — `:staging` on push to main, `:latest` on production promote, `:YYYYMMDD-HHMMSS` for rollback archive
- [ ] Automatic staging deploy on push to main
- [ ] Manual production approval gate via GitHub Environments
- [ ] Telegram notifications on deploy (staging + production)

## Phase 7 — Rollback Strategy (~half day)

- [ ] `infra/scripts/rollback.sh` — list available tags, pull and restart specified version
- [ ] `infra/scripts/rollback-migration.sh` — Alembic downgrade -1

## Phase 8 — Environment Parity (~half day)

- [ ] docker-compose.base.yml — shared service definitions (DRY across environments)
- [ ] docs/ENVIRONMENTS.md — comparison table (database, bot, API keys, features, URLs, deploy method)

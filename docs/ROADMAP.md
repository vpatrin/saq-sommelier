# Roadmap

Product phases below. Engineering discipline targets (testing, security, observability, SRE, platform, ML/MLOps) in [ENGINEERING.md](ENGINEERING.md).

---

## Product

### Phase 0 — Scaffolding ✅

Project structure, env config, Docker Compose baseline. (#1, #3–#5)

### Phase 1 — Scraping Exploration ✅

Sitemap fetch, HTML sampling, BeautifulSoup extraction, findings doc. (#6–#9)

### Phase 2 — Data Layer ✅

SQLAlchemy + Alembic in `core/`, Product model, DB writer. (#16–#18, #42)

### Phase 3 — Production Scraper ✅

Incremental sitemap scraper with delist detection, error handling, systemd timer. (#13–#15, #19, #49–#52, #83–#86)

### Phase 4 — API for Bot ✅

Search, filtering, facets, watches CRUD, structured exceptions. See [specs/TELEGRAM_BOT.md](specs/TELEGRAM_BOT.md). (#26, #33–#35, #41, #55, #98–#101)

### Phase 5 — Telegram Bot ✅

Bot scaffold, watch/alert system, store availability, UX polish, deep links. See [specs/DATA_PIPELINE.md](specs/DATA_PIPELINE.md). (#115–#121, #128, #138, #144, #149, #183, #212, #231–#233, #240, #243, #254, #273, #285, #345)

### Phase 6 — AI Layer (RAG + Claude) ✅

Adobe Live Search client, pgvector embeddings, Claude Haiku recommendations. See [specs/DATA_PIPELINE.md](specs/DATA_PIPELINE.md), [specs/RECOMMENDATIONS.md](specs/RECOMMENDATIONS.md). (#154–#156, #287–#289, #327)

### Phase 7 — Auth & Security ✅

Prerequisite for web app and protecting expensive endpoints.

- [x] Users table + Alembic migration — `role` column for admin gate (#353)
- [x] Telegram OAuth login endpoint (#354)
- [x] JWT token middleware (#355)
- [x] Guard all routes behind JWT except `/health` (#356)
- [x] Invite code access gate — admin-only `/api/admin/invites` endpoint, `invite_codes` table (#357)
- [x] Migrate bot allowlist from .env to users table (#358)
- [x] Admin bootstrap + user management — `make create-admin`, startup guard, list/deactivate endpoints

### Phase 8 — React Frontend (shell)

Web app ships before chat — auth, watches, and stores are already API-complete.

- [x] Scaffold + auth — Vite + React + Tailwind, Telegram OAuth login (invite code → Login Widget → JWT) (#382, #383, #384)
- [ ] Watch dashboard — watch list, availability status, add/remove
- [ ] Store picker — map or list view, add/remove preferred stores (replaces bot `/mystores`)
- [ ] "Enable Telegram alerts" onboarding — QR code / deep link to link web user to bot

### Phase 9 — Chat Endpoint

Wraps existing Haiku RAG pipeline for web consumption. No new AI architecture.

- [ ] Single-turn `/chat` endpoint — thin wrapper around recommendations service
- [ ] Chat session model + multi-turn — `chat_sessions` table, conversation history as pipeline context, sliding window
- [ ] SSE streaming — `text/event-stream` for progressive response display

### Phase 9b — Chat Interface

- [ ] Chat UI — message input, response display, SSE streaming, conversation history

### Phase 10 — MCP Server / Sonnet + Tools (optional)

Upgrade path from Haiku RAG to Claude with direct tool access. Either as MCP server (developer tooling) or Sonnet + tool use in `/chat` (product feature) — same architecture, different transport.

- [ ] Tool schema definitions — `search_wines()`, `get_product()`, `get_user_watches()`
- [ ] Agentic tool execution loop — Claude calls tools, backend executes, returns results
- [ ] MCP server entry point for Claude Code / Claude Desktop
- [ ] Pipeline benchmark — side-by-side quality comparison: Haiku RAG vs Sonnet + tools

### Ideas (unscoped)

- [ ] `/occasion` — context-aware suggestions ("wine for a BBQ", "gift for belle-mère") via Claude
- [ ] `/budget` — smart budget optimizer ("best rouge under $40") with value reasoning
- [ ] `/surprise` — discovery roulette that pushes outside comfort zone based on watch history
- [ ] `/gifter` — opt-in watch list sharing between friends for gift ideas
- [ ] `/blind` — blind tasting game: bot describes a wine, friends guess, track scores
- [ ] `/split` — group buy coordinator: share a bottle deal, track RSVPs among friends
- [ ] `/terroir` — region deep-dive with educational context + current SAQ inventory
- [ ] `/versus` — head-to-head wine comparison with Claude commentary on when to pick each
- [ ] `/cellar` — personal purchase tracker with taste profile insights over time
- [ ] `/digest` — weekly curated new arrivals summary, personalized to group preferences (#120)
- [ ] Rating aggregator — enrich products with Vivino scores and critic ratings; fuzzy name matching
- [ ] Price comparison vs France — compare SAQ prices to French retail (Wine-Searcher, Vinatis)
- [ ] Chrome extension — floating "Watch" button on SAQ product pages, triggers deep link to bot (or `POST /api/watches` with JWT after auth)
- [ ] Bilingual support — per-user language preference, static translation tables, bilingual bot/web responses (#134, #151–#153)

---

## Cross-cutting

### DevOps & CD Pipeline

**Production safety:**

- [x] Automated DB backups — weekly pg_dump + 30-day retention via systemd timer (#351)
- [ ] Cron failure alerts — Uptime Kuma push monitors for backup + scraper (#350)
- [x] Include alembic config in backend Docker image for in-container migrations (#227)

**CI hardening:**

- [x] Container security scan — Trivy on built images, catches OS-level CVEs that pip-audit misses (#360)
- [ ] Alembic migration smoke test — `upgrade head && check` against test DB (#316)

**CD pipeline:**

- [x] Build + Trivy + push to GHCR on tag push (#362)
- [x] docker-compose.prod.yml — GHCR images, restart policies, no dev volumes (#364)
- [x] Manual deploy via `./deploy/deploy.sh vX.Y.Z`

**Observability:**

- [ ] Request correlation — X-Request-ID middleware across bot → backend → DB (#315)

**Secrets management:**

- [ ] sops + age secrets — split `.env` into committed config + encrypted secrets, delete `.env.example`

**Learning backlog (future):**

- [ ] Staging environment — same VPS, separate port + DB, environment promotion pattern
- [ ] Kubernetes — container orchestration (when multi-node scaling is needed)
- [ ] ArgoCD / Flux — GitOps-style continuous delivery
- [ ] Terraform — infrastructure as code for VPS provisioning
- [ ] HashiCorp Vault — centralized secret management with RBAC and auto-rotation

### ~~RAG Eval + MLOps~~ — frozen

Revisit when pipeline quality needs iteration or for Phase 10 benchmark. See [specs/RECOMMENDATIONS.md](specs/RECOMMENDATIONS.md).

- [x] Eval framework — LLM-as-judge scoring with configurable rubric (#327)
- ~~Remaining items~~ — deferred


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
- [x] Watch dashboard — watch list, availability status, remove (#385)
- [x] Store picker — map or list view, add/remove preferred stores (replaces bot `/mystores`) (#388)
- [x] "Enable Telegram alerts" onboarding — deep link to bot on dashboard (#412)
- [x] Product search + add watch — search, filter (category/country/price/availability), watch from results (#386)

### Phase 9 — Chat Endpoint

Wraps existing Haiku RAG pipeline for web consumption. No new AI architecture.

- [x] Chat session + endpoints — session CRUD, single-turn message flow wrapping recommendations service (#425, #429)
- [x] Multi-turn context — conversation history as pipeline context, sliding window (#428, #434)
- [ ] SSE streaming endpoint — `text/event-stream` backend transport (#427)

### Phase 9b — Chat Interface

- [ ] Chat UI — message input, response display, conversation history (#426)
- [ ] SSE rendering — progressive token display in chat UI (depends on Phase 9 SSE endpoint)

### Phase 10 — Intent Router

Chat becomes the primary interface. Existing `is_recommendation()` check routes recommendation queries through the RAG pipeline; everything else (wine chat, food pairings, region questions, comparisons) goes direct to Claude. No granular intent taxonomy needed — if it's wine-related, the sommelier handles it.

- [ ] Chat-only path — non-recommendation wine queries skip the RAG pipeline, respond via Claude directly
- [ ] Structured data in chat — wine cards rendered inline when the sommelier references a product
- [ ] Prompt templates — suggested conversation starters on empty chat state ("Blind tasting challenge", "What pairs with...", "Compare two wines", "Explore a region")

### Phase 11 — Tasting Journal

Log wines you've tasted with 100-point ratings and tasting notes. SAQ catalog wines only (select by SKU). "Log tasting" action on product cards in search results and chat. Dedicated "My Tastings" page in sidebar.

- [ ] TastingNote model + migration — user_id, sku (FK), rating (0-100), notes, tasted_at
- [ ] Tasting CRUD endpoints — create, list (paginated, reverse-chronological), update, delete
- [ ] "Log tasting" inline form on product cards (search + chat)
- [ ] My Tastings page — reverse-chronological list, inline edit
- [ ] Surface "You rated: 92" on product cards in search results

### Phase 12 — Taste Profile

Build a user taste profile from watches, recommendation feedback, and tasting journal scores. MVP signals — no cellar data needed yet. Inject into recommendation prompts for personalization. Displayed as a sidebar widget, not a standalone page.

- [ ] Taste profile computation — aggregate signals into structured preferences (regions, grapes, price range, style)
- [ ] Adventure temperature — controls how exploratory vs conservative recommendations are (resolve UX scope — chat only, digest only, or both — during phase planning, before implementation)
- [ ] Profile context injection — pass taste profile + adventure setting to Claude for personalized recommendations
- [ ] Sidebar taste profile card — only shown after threshold (5+ tastings or 3+ watches), not before

### Phase 13 — Weekly Digest

Automated personalized summary of new/restocked wines matching user's taste profile. Delivered via Telegram DM (per-user, not group chat — #120 scope updated). This reintroduces the bot as a content delivery channel beyond alerts.

- [ ] Weekly job — query new/restocked products since last run
- [ ] Per-user personalization — filter by taste profile preferences
- [ ] Claude curation — summarize top picks with brief reasoning
- [ ] Telegram delivery — summary + link to full digest on web app
- [ ] Digest web page — weekly picks with full wine cards and tasting/cellar actions

### Phase 14 — Cellar

Track wines you have at home. SAQ catalog wines only. "Add to cellar" action on product cards. Quantity management on dedicated "My Cellar" page. Auto-remove when quantity hits 0. Cellar data feeds back into taste profile for richer signals.

- [ ] CellarEntry model + migration — user_id, sku (FK), quantity, added_at
- [ ] Cellar CRUD endpoints — add, list, update quantity, remove
- [ ] "Add to cellar" button on product cards
- [ ] My Cellar page — list with quantity +1/−1 controls
- [ ] Surface "In your cellar (×2)" on product cards in search results

### Side Projects (not product phases)

#### MCP Server / Sonnet + Tools

Dev tooling project — expose Coupette data to Claude Code / Claude Desktop via MCP. Same tool architecture as intent router but different transport. Not user-facing.

- [ ] Tool schema definitions — `search_wines()`, `get_product()`, `get_user_watches()`
- [ ] Agentic tool execution loop — Claude calls tools, backend executes, returns results
- [ ] MCP server entry point for Claude Code / Claude Desktop
- [ ] Pipeline benchmark — side-by-side quality comparison: Haiku RAG vs Sonnet + tools

### Ideas (unscoped)

- [ ] Usage & model controls — Sonnet vs Haiku toggle in UI, per-user API cost tracking, monthly usage limits
- [ ] Wine lists — named collections ("BBQ wines"), shareable via public link
- [ ] "Drink tonight" — context-aware quick pick from cellar ("I'm making lamb, what should I open?")
- [ ] "My Year in Wine" — annual recap (total tasted, avg score, top region, highest-rated, shareable)
- [ ] Chat-driven journal entry — log tastings via conversation ("just had the Mont-Redon, solid 88")
- [ ] Rating aggregator — enrich products with Vivino scores and critic ratings; fuzzy name matching
- [ ] Price comparison vs France — compare SAQ prices to French retail (Wine-Searcher, Vinatis)
- [ ] Chrome extension — floating "Watch" button on SAQ product pages (reuses bot URL paste SKU extraction logic)
- [ ] Bilingual support — per-user language preference, static translation tables, bilingual web/bot responses (#134, #151–#153)
- [ ] Wine tech sheets — external data enrichment beyond SAQ catalog (fiches techniques, critic notes)
- [ ] Bot `/recommend` deprecation — remove command, bot is alerts-only (cross-cutting chore, not a product idea)

---

## Cross-cutting

### UX Improvements

- [ ] Sidebar restructure — grouped nav (Discover / My Wines / My Stores) to scale for future phases
- [ ] Chat history in sidebar — recent session titles + "New chat" (Perplexity/ChatGPT pattern)
- [ ] Product card action overflow — expandable row for 3+ actions (Watch visible, tasting/cellar on expand) when tasting + cellar ship

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


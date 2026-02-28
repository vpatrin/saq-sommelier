# Roadmap

Product phases below. Engineering discipline targets (testing, security, observability, SRE, platform, ML/MLOps) in [ENGINEERING.md](ENGINEERING.md).

---

## Product

### Phase 0 — Scaffolding ✅

- [x] Project structure (#1)
- [x] Environment config (#5)
- [x] Docker Compose baseline (#3, #4)

### Phase 1 — Scraping Exploration ✅

- [x] Fetch and parse sitemap (#6)
- [x] Download raw HTML samples (#7)
- [x] BeautifulSoup extraction script (#8)
- [x] Document findings (#9)

### Phase 2 — Data Layer ✅

- [x] SQLAlchemy setup + DB connection (#16)
- [x] Alembic init + migrate to core/ (#42)
- [x] Product model + first migration (#17)
- [x] DB writer (#18)

### Phase 3 — Production Scraper ✅

- [x] Sitemap fetcher service (#14)
- [x] Product parser service (#15)
- [x] Scraper orchestrator (#19)
- [x] Scraper Dockerfile (#13)
- [x] Fetch all sub-sitemaps (PR #83)
- [x] Error handling (PR #86)
- [x] ScraperSettings validators (#84)
- [x] Incremental scraping via lastmod (#50)
- [x] Detect delisted products (#51)
- [x] Run summary + exit codes (#52)
- [x] Weekly cronjob (#49) — systemd timer + Compose service

### Phase 4 — API for Bot ✅

Backend endpoints driven by Telegram bot needs. See [specs/TELEGRAM_BOT.md](specs/TELEGRAM_BOT.md) for full design.

- [x] Product list endpoint (#33)
- [x] Product detail endpoint (#34)
- [x] Product search + filtering (#35)
- [x] Database indexes (#26)
- [x] Structured exception handling (#41)
- [x] Exclude delisted + available filter (#98)
- [x] Catalog facets endpoint (#55)
- [x] Sort by recent + random product (#99, #100)
- [x] Watches CRUD (#101) — powers `/watch`, `/unwatch`, `/alerts`
- ~~Price history tracking (#57)~~ — descoped, SAQ prices are regulated

### Phase 5 — Telegram Bot ✅

- [x] Bot scaffold (`bot/` service, python-telegram-bot) (#115)
- [x] Bot API client — typed httpx wrapper for backend endpoints (#116)
- [x] Inline keyboard filters — shared formatters, keyboards, filter callbacks (#118, #161)
- [x] `/new` — recently added/updated wines with filters (#118)
- [x] `/random` — random wine with filters (#118)
- [x] `/watch`, `/unwatch`, `/alerts` — passive watch list + on-demand status check (#119)
- [x] Post-scrape restock notifications — proactive alerts when watched products come back (#138)
- [x] Destock notifications — alert users when watched products go out of stock (#212)
- [x] Bot Dockerfile + Compose service (#121, #44)

### Phase 5a — Bot UX Polish ✅

- [x] Improve category selection UX (#162)
- [x] "Back" button to return to previous results (#163) — resolved by persistent reply keyboard
- [x] Main menu with navigation buttons (#164)
- [x] Disable link preview for multi-result messages (#165)
- [x] Paginated results with next/previous buttons (#167)
- [x] Auto-recap watch list after /watch and /unwatch (#183)

### Phase 5b — Store Availability

See [specs/STORE_AVAILABILITY.md](specs/STORE_AVAILABILITY.md) for API reference and engineering plan.

- [x] Store directory scrape (#128) — one-shot `stores` table (401 rows)
- [x] Emit destock events when availability flips True → False (#144)
- ~~Extract `magento_id` from HTML (#148)~~ — eliminated, GraphQL batch lookup used instead
- [x] `UserStorePreference` model + migration (#231)
- [x] `/stores` API endpoints — nearby + user preference CRUD (#232)
- [x] `/mystores` bot command — GPS-based store picker (#233)
- [x] Per-product store availability checker — GraphQL resolve + AJAX fetch + diff alerts (#149)
- ~~Filter by store availability (#150)~~ — out of scope, SAQ.com does this natively

### Phase 5c — Bilingual Support

- [ ] Per-user language preference (FR default, EN opt-in) (#134)
- [ ] Static translation tables for structured fields (#151)
- [ ] Bilingual bot responses, button labels, and help text (#152)
- [ ] Bilingual formatters (#153)

### Phase 6 — AI Layer (RAG + Claude)

- [ ] ChromaDB + embeddings (#154)
- [ ] Claude API integration (#155)
- [ ] `/recommend` — natural language recommendations via Telegram (#156)
- [ ] Weekly digest — LLM-curated summary posted to group chat after scraper run (#120)

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

---

## Timeline Estimate

Discipline targets referenced in [ENGINEERING.md](ENGINEERING.md).

```text
Phase 5 (Telegram Bot)          ~5 days     ✅ DONE
  + Testing 1-2: unit tests, integration tests       ~3 days
  + Platform 1: Makefile, dev environment             ~1 day
  + Env Seg 1-2: config foundation, local dev         ~1 day

Deploy to production            ~2 days
  + Platform 2-3: prod Docker, CI/CD pipeline         ~2 days
  + Env Seg 4-5: staging environment, prod hardening  ~2 days

Phase 6 (AI Layer)              ~10 days
  + ML/MLOps 6a-6d: embeddings, Claude, RAG, eval
  + Observability 1: request/LLM/RAG logging
  + SRE 1-2: SLOs, health checks, alerting
  + Testing 3: ML tests

Post-deployment polish          ~8 days
  + SRE 3-6: runbook, load testing, toil, capacity
  + Observability 2-4: Grafana, structured logs, alerting
  + Platform 4-5: IaC, backups
  + Testing 4-5: contract tests, E2E
  + Env Seg 6-7: CI/CD promotion, rollback

Advanced / Portfolio            ~10 days
  + ML 7-8: optimization, vision, A/B testing
  + Observability 5-6: Prometheus, Loki
  + Platform 6-7: security hardening, dashboards as code
  + SRE 7: on-call documentation

Total: ~40 days at current pace
Core product (Phases 5-6 + deploy): ~17 days
```

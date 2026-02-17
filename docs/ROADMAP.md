# Roadmap

## Product

### Phase 0 — Scaffolding (done)

- [x] Project structure (#1)
- [x] Environment config (#5)
- [x] Docker Compose baseline (#3, #4)

### Phase 1 — Scraping Exploration (done)

- [x] Fetch and parse sitemap (#6)
- [x] Download raw HTML samples (#7)
- [x] BeautifulSoup extraction script (#8)
- [x] Document findings (#9)

### Phase 2 — Data Layer (done)

- [x] SQLAlchemy setup + DB connection (#16)
- [x] Alembic init + migrate to core/ (#42)
- [x] Product model + first migration (#17)
- [x] DB writer (#18)

### Phase 3 — Production Scraper (done)

- [x] Sitemap fetcher service (#14)
- [x] Product parser service (#15)
- [x] Scraper orchestrator (#19)
- [x] Scraper Dockerfile (#13)
- [x] Fetch all sub-sitemaps (PR #83)
- [x] Error handling (PR #86)
- [x] ScraperSettings validators (#84)
- [x] Incremental scraping via lastmod (#50, PR #94)
- [x] Detect delisted products (#51, PR #96)
- [x] Run summary + exit codes (#52, PR #95)
- [x] Weekly cronjob (#49, PR #97) — systemd timer + Compose service

### Phase 4 — API for Bot (done)

Backend endpoints driven by Telegram bot needs. See [TELEGRAM_BOT.md](TELEGRAM_BOT.md) for full design.

- [x] Product list endpoint (#33)
- [x] Product detail endpoint (#34)
- [x] Product search + filtering (#35)
- [x] Database indexes (#26)
- [x] Structured exception handling (#41)
- [x] Exclude delisted + available filter (#98, PR #103)
- [x] Catalog facets endpoint (#55, PR #105)
- [x] Sort by recent + random product (#99, #100, PR #107)
- [x] Watches CRUD (#101, PR #112) — powers `/watch`, `/unwatch`, `/alerts`
- ~~Price history tracking (#57)~~ — descoped, SAQ prices are regulated

### Phase 5 — Telegram Bot

- [ ] Bot scaffold (`bot/` service, python-telegram-bot)
- [ ] `/search` — search wines with inline keyboard filters
- [ ] `/new` — recently added/updated wines with filters
- [ ] `/random` — random wine with filters
- [ ] `/watch`, `/unwatch`, `/alerts` — availability/restock alerts
- [ ] Weekly digest — proactive post to group chat after scraper run
- [ ] Bot Dockerfile + Compose service

### Phase 6 — AI Layer (RAG + Claude)

- [ ] ChromaDB + embeddings
- [ ] Claude API integration
- [ ] `/recommend` — natural language recommendations via Telegram

## Infrastructure / Chores

Ongoing work that runs alongside the product phases.

- [x] CI linting, caching, Hadolint, coverage thresholds (#2, #72, #73, #62)
- [x] Dependabot (#61)
- [x] Dockerfile hardening + Compose profiles (#3, #4)
- [x] Pydantic Settings + BackendSettings (#5, PR #80)
- [x] CORS + input validation (PR #80)
- [x] Rename shared/ to core/, move Alembic (#38, #39, #42)
- [x] PR template, repo topics, README cleanup (#81, #64, #37)
- [x] Type hints + docstring cleanup (PR #82)
- [x] Backend logging (#85)
- [ ] Full Docker dev environment (#44)
- [ ] Port assignment convention (#53)
- [ ] Observability — tool choice (Loki+Promtail vs alternatives), centralized logging, Grafana dashboards

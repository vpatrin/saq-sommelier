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

### Phase 3 — Production Scraper (done, hardening in progress)

- [x] Sitemap fetcher service (#14)
- [x] Product parser service (#15)
- [x] Scraper orchestrator (#19)
- [x] Scraper Dockerfile (#13)
- [x] Fetch all sub-sitemaps (PR #83)
- [ ] Error handling + observability (#78)
- [ ] ScraperSettings validators (#84)
- [ ] Incremental scraping via lastmod (#50)
- [ ] Detect delisted products (#51)
- [ ] Health metrics + run summary (#52)
- [ ] Weekly cronjob (#49)

### Phase 4 — API + Business Logic (in progress)

- [x] Product list endpoint (#33)
- [x] Product detail endpoint (#34)
- [x] Product search + filtering (#35)
- [x] Database indexes (#26)
- [x] Structured exception handling (#41)
- [ ] Catalog facets endpoint (#55)
- [ ] Stats summary endpoint (#56)
- [ ] Price history tracking (#57)
- [ ] In-store availability tracking (#59)
- [ ] Auth (if needed)

### Phase 5 — Telegram Bot

- [ ] Basic bot scaffold
- [ ] Wire to API — query wines from chat
- [ ] Availability alerts (#58)

### Phase 6 — AI Layer (RAG + Claude)

- [ ] ChromaDB + embeddings
- [ ] Claude API integration
- [ ] Natural language recommendations via Telegram

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

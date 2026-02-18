# Roadmap

One project, six disciplines. Detailed task breakdowns in [roadmaps/](roadmaps/).

| Discipline | Roadmap |
| --- | --- |
| ML / MLOps | [ml-mlops.md](roadmaps/ml-mlops.md) |
| Testing | [testing.md](roadmaps/testing.md) |
| SRE | [sre.md](roadmaps/sre.md) |
| Platform Engineering | [platform-engineering.md](roadmaps/platform-engineering.md) |
| Observability | [observability.md](roadmaps/observability.md) |
| Environment Segregation | [environment-segregation.md](roadmaps/environment-segregation.md) |

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

Backend endpoints driven by Telegram bot needs. See [TELEGRAM_BOT.md](TELEGRAM_BOT.md) for full design.

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

### Phase 5 — Telegram Bot

- [x] Bot scaffold (`bot/` service, python-telegram-bot) (#115)
- [x] Bot API client — typed httpx wrapper for backend endpoints (#116)
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

---

## Timeline Estimate

Phase numbers reference the [discipline roadmaps](roadmaps/) linked above.

```text
Phase 5 (Telegram Bot)          ~5 days     ← YOU ARE HERE
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

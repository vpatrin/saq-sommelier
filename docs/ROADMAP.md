# Roadmap

## Phase 0 — Scaffolding

1. Project structure
2. Environment config
3. Docker Compose baseline
4. CI linting

## Phase 1 — Scraping Exploration

5. Fetch and parse sitemap
6. Download raw HTML samples
7. BeautifulSoup extraction script
8. Document findings

## Phase 2 — Data Layer

9. SQLAlchemy setup + DB connection
10. Alembic init
11. Product model + first migration
12. DB writer

## Phase 3 — Production Scraper

13. Sitemap fetcher service
14. Product parser service
15. Scraper orchestrator
16. Scraper Dockerfile

## Phase 4 — API + Business Logic

17. Products endpoint (search, filter, list)
18. Business logic — the interesting part (price tracking? new arrivals? "best value" scoring? depends on what the data reveals)
19. Auth if needed

## Phase 5 — Telegram Bot

20. Basic bot scaffold
21. Wire to API — query wines from chat

## Phase 6 — AI Layer (RAG + Claude)

22. ChromaDB + embeddings
23. Claude API integration
24. Natural language recommendations via Telegram

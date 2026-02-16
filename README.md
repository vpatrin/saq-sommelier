# SAQ Sommelier

AI-powered wine recommendation engine built on the SAQ (Quebec liquor board) product catalog.

[![CI](https://github.com/vpatrin/saq-sommelier/actions/workflows/ci.yml/badge.svg)](https://github.com/vpatrin/saq-sommelier/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![backend coverage](.github/badges/coverage-backend.svg)
![scraper coverage](.github/badges/coverage-scraper.svg)

Scrapes ~38k products from the SAQ public sitemap, stores structured wine data in PostgreSQL, and serves it through a FastAPI API. A Telegram bot will provide natural language recommendations powered by Claude.

## Architecture

```mermaid
graph LR
    SAQ[SAQ.com]
    Scraper[Scraper]
    DB[(PostgreSQL)]
    API[FastAPI]
    Claude[Claude API]
    Bot[Telegram Bot]
    Web[React Dashboard]

    SAQ -- sitemap XML --> Scraper
    Scraper -- write --> DB
    DB -- read --> API
    API --> Claude
    API --> Bot
    API --> Web

    style Bot stroke-dasharray: 5 5
    style Web stroke-dasharray: 5 5
    style Claude stroke-dasharray: 5 5
```

*Dashed = planned. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full details.*

## Quick start

```bash
make install              # install all dependencies (Poetry)
cp .env.example .env      # defaults work as-is
make up                   # start PostgreSQL (localhost:5432)
make migrate              # create database tables
make scrape               # populate the database (~38k products)
make dev                  # start the backend (localhost:8000)
```

## Development

```bash
make lint          # ruff check
make format        # ruff format
make test          # pytest (all services)
make coverage      # tests + coverage badges
make migrate       # alembic upgrade head
make build         # docker build
make up / down     # docker compose (postgres)
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for database setup options and full workflow.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system design, project structure, tech decisions
- [Data Flow](docs/DATA_FLOW.md) — three-schema boundary design
- [Development](docs/DEVELOPMENT.md) — database setup, environment config, dev workflow
- [Migrations](docs/MIGRATIONS.md) — Alembic setup, workflow, and troubleshooting
- [Roadmap](docs/ROADMAP.md) — project phases and progress

## Legal

SAQ data is scraped ethically via their public sitemap (listed in `robots.txt`). Rate-limited to 2s between requests with transparent bot identification.

## License

MIT

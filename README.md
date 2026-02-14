# SAQ Sommelier

AI-powered wine recommendation engine built on the SAQ (Quebec liquor board) product catalog.

[![CI](https://github.com/vpatrin/saq-sommelier/actions/workflows/ci.yml/badge.svg)](https://github.com/vpatrin/saq-sommelier/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![backend coverage](.github/badges/coverage-backend.svg)
![scraper coverage](.github/badges/coverage-scraper.svg)

## What it does

Scrapes the SAQ product catalog via their public sitemap, stores structured wine data in PostgreSQL, and will eventually provide AI-powered recommendations through a Telegram bot and web interface.

**Current status:** Scraper pipeline works end-to-end (sitemap parsing, HTML extraction, database upsert). Backend and AI layers are next.

## Stack

| Layer      | Technology                                     |
| ---------- | ---------------------------------------------- |
| Backend    | Python 3.12, FastAPI                           |
| Database   | PostgreSQL 16 (async via SQLAlchemy + asyncpg) |
| Migrations | Alembic                                        |
| Scraper    | httpx, BeautifulSoup4, lxml                    |
| AI         | Claude API (planned)                           |
| Frontend   | React + Vite (planned)                         |
| Infra      | Docker, Docker Compose, Caddy                  |

## Project structure

```
saq-sommelier/
├── backend/          # FastAPI API server
├── scraper/          # SAQ product catalog scraper
├── shared/           # Shared DB models, base, config
├── scripts/          # Exploration and utility scripts
├── .github/
│   ├── badges/       # Auto-generated coverage badges
│   └── workflows/ci.yml
├── Makefile
└── docker-compose.yml
```

Each service has its own `pyproject.toml`, `Dockerfile`, and Poetry environment. Services communicate through PostgreSQL, not by importing each other.

## Getting started

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- PostgreSQL running locally (we use a shared instance via Docker)

### Setup

```bash
# Install all dependencies
make install

# Copy env file and configure DB credentials
cp scraper/.env.example scraper/.env

# Run database migrations
cd scraper && poetry run alembic upgrade head && cd ..
```

### Run the scraper

```bash
make scrape
```

### Run the dev server

```bash
make dev
```

## Development

```bash
make lint          # Lint all services (ruff)
make format        # Auto-format all services
make test          # Run all tests
make coverage      # Run tests with coverage + update badges
make clean         # Remove caches and coverage artifacts
```

## Legal

SAQ product data is scraped ethically via their public sitemap (listed in `robots.txt`). Rate-limited to 2s between requests with transparent bot identification. See [scripts/FINDINGS.md](scripts/FINDINGS.md) for full analysis.

## License

MIT

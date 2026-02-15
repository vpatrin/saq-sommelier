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
├── core/             # Core infrastructure (models, config, logging)
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
- PostgreSQL (see [Database](#database) below)

### Setup

```bash
# Install all dependencies
make install

# Copy env file and configure DB credentials
cp .env.example .env

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

## Database

Two options for running PostgreSQL locally:

### Option A: Standalone (Docker Compose)

Spins up a dedicated postgres container — no external dependencies.

```bash
make up      # starts postgres + backend (docker compose --profile dev)
make down    # stops everything (data persists in pgdata volume)
```

The compose `dev` profile starts a postgres:17-alpine instance on the internal Docker network. Backend and scraper connect to it automatically via `DB_HOST=postgres`.

### Option B: Shared PostgreSQL instance

If you run multiple projects on the same machine (or VPS), you can use a shared PostgreSQL instance like [shared-postgres](https://github.com/vpatrin/shared-postgres) instead.

```bash
# 1. Start shared-postgres (separate repo, runs on localhost:5432)
cd ../shared-postgres && make up

# 2. Bare-metal: just works — .env has DB_HOST=localhost by default
make scrape
make dev

# 3. Docker containers: override DB_HOST to reach the host machine
DB_HOST=host.docker.internal docker compose up backend
DB_HOST=host.docker.internal docker compose run --rm scraper
```

`host.docker.internal` is a Docker Desktop (macOS/Windows) DNS name that resolves to the host machine. On Linux, use `--network=host` or the host's IP instead.

> **Note:** Without `--profile dev`, the compose postgres service doesn't start. `depends_on` uses `required: false`, so backend and scraper work fine without it.

## Development

```bash
make lint          # Lint all services (ruff)
make format        # Auto-format all services
make test          # Run all tests
make coverage      # Run tests with coverage + update badges
make build         # Build all Docker images
make clean         # Remove caches and coverage artifacts
```

## Legal

SAQ product data is scraped ethically via their public sitemap (listed in `robots.txt`). Rate-limited to 2s between requests with transparent bot identification. See [scripts/FINDINGS.md](scripts/FINDINGS.md) for full analysis.

## License

MIT

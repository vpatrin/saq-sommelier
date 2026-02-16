# Development Guide

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker (for PostgreSQL)

## Setup

```bash
make install              # install all dependencies
cp .env.example .env      # defaults work as-is
make up                   # start PostgreSQL (localhost:5432)
make migrate              # create database tables
make scrape               # populate the database (~38k products)
make dev                  # start the backend (localhost:8000)
```

## Database

### Default: Docker Compose

`make up` starts a postgres:16-alpine container on `localhost:5432`. Bare-metal tools (alembic, `make dev`, `make scrape`) connect to it directly. GUI tools like DBeaver can also connect to `localhost:5432` with the credentials from `.env`.

```bash
make up                   # start postgres
make down                 # stop postgres (data persists in pgdata volume)
```

### Using an existing PostgreSQL instance

If you already have PostgreSQL running (e.g., [shared-postgres](https://github.com/vpatrin/shared-postgres) or a system install), skip `make up` and update `.env`:

```bash
DB_HOST=localhost         # or your postgres host
DB_PORT=5432              # or your postgres port
```

Everything else (`make migrate`, `make scrape`, `make dev`) works the same.

## Environment

All services read from a single root `.env` file. See [.env.example](../.env.example) for all available variables.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_USER` | yes | — | PostgreSQL username |
| `DB_PASSWORD` | yes | — | PostgreSQL password |
| `DB_NAME` | yes | — | Database name |
| `DB_HOST` | no | `localhost` | Database host |
| `DB_PORT` | no | `5432` | Database port |
| `ENVIRONMENT` | no | `development` | `development` or `production` |
| `LOG_LEVEL` | no | `INFO` | Logging level |
| `DEBUG` | no | `false` | Debug mode |
| `DATABASE_ECHO` | no | `false` | Log SQL queries |

## Make targets

```bash
# Development
make install       # poetry install for all services
make dev           # uvicorn backend on localhost:8000
make scrape        # run the scraper
make migrate       # alembic upgrade head
make reset-db      # wipe all data and recreate tables

# Quality
make lint          # ruff check (all services)
make format        # ruff format (all services)
make test          # pytest (all services)
make coverage      # tests + coverage badges

# Docker
make build         # build backend Docker image
make up            # start postgres (local dev)
make down          # stop postgres

# Cleanup
make clean         # remove __pycache__, .pytest_cache, .ruff_cache
```

## Working on the scraper

The scraper is a one-shot batch job (not a long-running service). It fetches the SAQ sitemap and upserts products into PostgreSQL. See [SCRAPER.md](SCRAPER.md) for production scheduling and operations.

```bash
make scrape               # run the scraper (upserts ~38k products)
```

When iterating on parser logic, wipe the database first to test from a clean state:

```bash
make reset-db && make scrape
```

`make reset-db` runs `alembic downgrade base && alembic upgrade head` — drops all tables and recreates them, so the scraper starts fresh. This also validates that your migrations work in both directions.

## Working on the backend

The backend runs with hot reload — edit code, save, and uvicorn restarts automatically.

```bash
make dev                  # start on localhost:8000
```

API docs (Swagger UI) are available at [localhost:8000/docs](http://localhost:8000/docs).

The backend expects a populated database. If you see empty responses, run `make scrape` first.

## Docker

```bash
make up                   # start postgres for local dev
make down                 # stop postgres
make build                # build backend Docker image
```

Full Docker development (backend + scraper in containers) is tracked in [#44](https://github.com/vpatrin/saq-sommelier/issues/44).

## Running tests

```bash
# All services
make test

# Single service
make test-backend
make test-scraper

# With coverage
make coverage
```

Tests use an in-memory SQLite database by default (no PostgreSQL required).

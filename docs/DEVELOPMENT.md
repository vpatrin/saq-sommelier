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
make dev-scrape           # populate the database (~38k products)
make dev-backend          # start the backend (localhost:8000)
```

## Database

### Default: Docker Compose

`make up` starts a postgres:16-alpine container on `localhost:5432`. Bare-metal tools (alembic, `make dev-backend`, `make dev-scrape`) connect to it directly. GUI tools like DBeaver can also connect to `localhost:5432` with the credentials from `.env`.

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

Everything else (`make migrate`, `make dev-scrape`, `make dev-backend`) works the same.

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
| `TELEGRAM_BOT_TOKEN` | bot only | — | Token from @BotFather |
| `BACKEND_URL` | no | `http://localhost:8000` | API URL for the bot |

## Make targets

```bash
# Development
make install       # poetry install for all services
make dev-backend   # uvicorn backend on localhost:8000
make dev-bot       # telegram bot in polling mode
make dev-scrape    # run the scraper
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
make dev-scrape           # run the scraper (upserts ~38k products)
```

When iterating on parser logic, wipe the database first to test from a clean state:

```bash
make reset-db && make dev-scrape
```

`make reset-db` runs `alembic downgrade base && alembic upgrade head` — drops all tables and recreates them, so the scraper starts fresh. This also validates that your migrations work in both directions.

## Working on the backend

The backend runs with hot reload — edit code, save, and uvicorn restarts automatically.

```bash
make dev-backend          # start on localhost:8000
```

API docs (Swagger UI) are available at [localhost:8000/docs](http://localhost:8000/docs).

The backend expects a populated database. If you see empty responses, run `make dev-scrape` first.

## Working on the bot

The Telegram bot runs in polling mode locally — no webhook or public URL needed.

```bash
make dev-bot              # start polling (requires TELEGRAM_BOT_TOKEN in .env)
```

Get a token from [@BotFather](https://t.me/BotFather) on Telegram and add it to `.env`. The bot calls the backend API, so run `make dev-backend` in another terminal first.

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
make test-bot

# With coverage
make coverage
```

Tests use an in-memory SQLite database by default (no PostgreSQL required).

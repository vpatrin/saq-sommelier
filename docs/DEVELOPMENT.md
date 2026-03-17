# Development Guide

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Node.js 24+ and [Yarn](https://classic.yarnpkg.com/) (for frontend)
- Docker (for PostgreSQL)

## Setup

```bash
make install              # install all Python + frontend dependencies
cp .env.example .env      # fill in required values (see Environment below)
make run-db               # start PostgreSQL (localhost:5432)
make migrate              # create database tables
make create-admin         # seed admin user (required — backend won't start without it)
make dev-scraper          # populate the database (~14k wine products)
make dev-backend          # start the backend (localhost:8001)
make dev-frontend         # start the frontend (localhost:5173)
```

Or skip Poetry entirely and run everything in Docker:

```bash
cp .env.example .env      # fill in required values
make run                  # postgres + backend + bot (with hot reload)
make migrate              # create database tables
make create-admin         # seed admin user
make run-scraper          # populate the database
```

Note: the frontend runs bare-metal only (`yarn dev`) — not in Docker. Hot reload matters.

## Environment

All services read from a single root `.env` file. See [.env.example](../.env.example) for all available variables.

### Required

| Variable | Description |
|----------|-------------|
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_NAME` | Database name |
| `ADMIN_TELEGRAM_ID` | Your Telegram user ID (for admin bootstrap) |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DEBUG` | `false` | Debug mode |
| `DATABASE_ECHO` | `false` | Log SQL queries |
| `SCRAPE_LIMIT` | `500` | Max products to scrape per run (0 = full catalog) |

### Service-specific

| Variable | Required for | Description |
|----------|-------------|-------------|
| `TELEGRAM_BOT_TOKEN` | bot | Token from @BotFather |
| `BOT_SECRET` | bot + backend | Shared secret for bot → backend auth |
| `BACKEND_URL` | bot | API URL (default: `http://localhost:8001`) |
| `NOTIFICATION_POLL_INTERVAL` | bot | Notification poll interval in seconds |
| `ANTHROPIC_API_KEY` | backend | Claude API key (intent parsing, curation, chat) |
| `OPENAI_API_KEY` | backend + scraper | OpenAI API key (embeddings) |
| `JWT_SECRET_KEY` | backend | JWT signing key |
| `CORS_ORIGINS` | backend | Allowed origins (default: `["http://localhost:5173"]`) |
| `VITE_TELEGRAM_BOT_USERNAME` | frontend | Bot username for Telegram Login Widget |

## Make targets

```bash
# Development
make install         # poetry install (all Python services) + yarn install (frontend)
make dev-backend     # uvicorn backend on localhost:8001
make dev-bot         # telegram bot in polling mode
make dev-scraper     # run the scraper
make dev-frontend    # vite dev server on localhost:5173
make migrate         # alembic upgrade head
make create-admin    # seed admin user
make reset-db        # wipe all data and recreate tables

# Quality
make lint            # ruff check (Python) + eslint + typecheck (frontend)
make format          # ruff format (Python) + prettier (frontend)
make test            # pytest (all Python services)
make coverage        # tests + coverage badges

# Docker
make build           # build all service images
make run             # full Docker dev stack (postgres + backend + bot)
make run-db          # postgres only (for bare-metal dev)
make run-scraper     # one-shot scrape (Docker)
make down            # stop all containers

# Cleanup
make clean           # remove __pycache__, .pytest_cache, .ruff_cache
```

## Working on the frontend

The frontend is a React SPA built with Vite, TypeScript, Tailwind CSS, and shadcn/ui. It runs bare-metal (not in Docker) for fast hot reload.

```bash
make dev-frontend         # vite dev server on localhost:5173
```

The frontend expects the backend running on `localhost:8001`. Run `make dev-backend` in another terminal.

```bash
# Lint and format
make lint-frontend        # eslint + typecheck + format check
make format-frontend      # prettier

# Build for production
make build-frontend       # typecheck + vite build
```

## Working on the scraper

The scraper is a one-shot batch job (not a long-running service). It fetches the SAQ sitemap and upserts products into PostgreSQL. See [OPERATIONS.md](OPERATIONS.md) for production scheduling.

```bash
make dev-scraper          # run the scraper (upserts ~14k wine products)
```

When iterating on parser logic, wipe the database first to test from a clean state:

```bash
make reset-db && make dev-scraper
```

`make reset-db` runs `alembic downgrade base && alembic upgrade head` — drops all tables and recreates them. This also validates that your migrations work in both directions.

## Working on the backend

The backend runs with hot reload — edit code, save, and uvicorn restarts automatically.

```bash
make dev-backend          # start on localhost:8001
```

API docs (Swagger UI) are available at [localhost:8001/docs](http://localhost:8001/docs).

The backend expects a populated database. If you see empty responses, run `make dev-scraper` first.

## Working on the bot

The Telegram bot runs in polling mode locally — no webhook or public URL needed.

```bash
make dev-bot              # start polling (requires TELEGRAM_BOT_TOKEN in .env)
```

Get a token from [@BotFather](https://t.me/BotFather) on Telegram and add it to `.env`. The bot calls the backend API, so run `make dev-backend` in another terminal first.

## Docker

Two workflows, choose whichever fits:

### Full stack in Docker (no Poetry required)

```bash
make run                  # postgres + backend + bot (hot reload via volume mounts)
make run-scraper          # one-shot scrape (docker compose run)
make down                 # stop everything
```

Volume mounts and `--reload` are baked into `docker-compose.yml`. Edit code locally, changes are picked up in the container. For the bot, restart the container after changes (`docker compose restart bot`).

### Bare-metal dev (Poetry + containerized postgres)

```bash
make run-db               # postgres only
make dev-backend          # uvicorn with --reload
make dev-frontend         # vite with HMR
make dev-bot              # telegram bot polling
make dev-scraper          # one-shot scrape
make down                 # stop postgres
```

### Building images

```bash
make build                # build all service images (backend, scraper, bot)
make build-backend        # build backend only
make build-scraper        # build scraper only
make build-bot            # build bot only
```

## Running tests

```bash
# All Python services
make test

# Single service
make test-backend
make test-scraper
make test-bot

# With coverage
make coverage
```

Tests use mocked database sessions and external API calls (no live PostgreSQL or API keys required).

## Migrations

The model (`core/db/models.py`) is the source of truth for the DB schema. Alembic generates migrations by diffing the model against the live database.

### Workflow

```bash
# 1. Edit the model
vim core/db/models.py

# 2. Autogenerate migration (requires running DB)
make revision msg="add alcohol column"

# 3. Review the generated file in core/alembic/versions/

# 4. Apply
make migrate

# 5. Commit model + migration together
git add core/db/models.py core/alembic/versions/xxxx_*.py
```

### Rules

- **Model = source of truth** — columns, indexes, constraints all defined on the model
- **Forward-only in production** — never run `downgrade()` in prod; write a new migration to fix mistakes
- **`downgrade()` is a dev convenience** — `make reset-db` uses it to replay from scratch
- **Autogenerate detects** new/removed columns, indexes, type changes — but NOT column renames (sees drop+add) or data migrations; hand-add those

### Quick reference

| Task | Command |
| --- | --- |
| Apply all pending | `make migrate` |
| Generate migration | `make revision msg="description"` |
| Full reset (dev only) | `make reset-db` |
| Check current version | `cd core && poetry run alembic current` |
| Show history | `cd core && poetry run alembic history` |

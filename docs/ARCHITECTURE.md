# Architecture

## Overview

Coupette is a wine discovery and recommendation tool built on data from the SAQ (Société des alcools du Québec) catalog. It scrapes ~14k wine products, stores them in PostgreSQL with pgvector embeddings, and serves them through a FastAPI API. A Telegram bot and React web app provide natural language recommendations powered by Claude.

Designed as a **modular monolith** for a solo developer serving ~20 users. Services are independently deployable containers that communicate through PostgreSQL — not by importing each other's code.

## System diagram

```
                          ┌────────────────────────┐
                          │        CLIENTS         │
                          │                        │
                          │  React Web App         │
                          │  Telegram Bot          │
                          └───────────┬────────────┘
                                     │
                                HTTPS (Caddy)
                                     │
                          ┌──────────▼───────────┐
                          │   BACKEND (FastAPI)   │
                          │                       │
                          │  /health              │
                          │  /api/auth            │
                          │  /api/products        │
                          │  /api/stores          │
                          │  /api/watches         │
                          │  /api/recommendations │
                          │  /api/chat            │
                          │  /api/admin           │
                          │                       │
                          └──┬──────┬────────┬────┘
                             │      │        │
                    ┌────────▼──┐ ┌─▼──────┐ ┌▼────────────┐
                    │ PostgreSQL│ │ Claude  │ │ OpenAI      │
                    │ + pgvector│ │ Haiku   │ │ Embeddings  │
                    │           │ │         │ │             │
                    │ products  │ │ Intent  │ │ text-embed- │
                    │ users     │ │ Curation│ │ ding-3-large│
                    │ watches   │ │ Chat    │ └─────────────┘
                    │ chat      │ └────────┘
                    │ stores    │
                    └────────▲──┘
                             │
                             │ writes
                             │
                    ┌────────┴────────────┐
                    │  SCRAPER            │
                    │                     │
                    │  Sitemap → HTML     │
                    │  → Adobe API enrich │
                    │  → Upsert to DB     │
                    │  → Embed (pgvector) │
                    │                     │
                    │  Weekly cron         │
                    │  2s/req rate limit   │
                    │  ~14k wine products  │
                    └─────────────────────┘
```

## Data flow

| Path | Flow |
|------|------|
| **Write** | SAQ.com → Scraper → PostgreSQL |
| **Embed** | Product text → OpenAI embeddings → pgvector |
| **Read** | Client → Caddy → FastAPI → PostgreSQL → Response |
| **Recommend** | Client → FastAPI → Claude (intent) → pgvector (retrieval) → Claude (curation) → Response |
| **Chat** | Client → FastAPI → Claude (sommelier) → Response |

## Project structure

```
coupette/
├── backend/          FastAPI API (reads from DB, calls Claude + OpenAI)
│   ├── api/          HTTP endpoints (auth, products, stores, watches, chat, admin)
│   ├── repositories/ Database queries (SQLAlchemy)
│   ├── services/     Business logic (intent, recommendations, curation, sommelier, chat)
│   ├── schemas/      Pydantic request/response models (API contract)
│   ├── app.py        App entry point + router registration
│   └── tests/
├── bot/              Telegram bot (calls backend API)
│   ├── bot/          Handlers, formatters, keyboards, API client
│   └── tests/
├── scraper/          Standalone scraper (writes to DB)
│   └── src/          Sitemap fetcher, HTML parser, DB upsert, embeddings, availability
├── core/             Shared package (Poetry path dependency)
│   ├── db/           SQLAlchemy base, models, session factory
│   ├── config/       Pydantic Settings (DB connection)
│   └── logging.py    Loguru setup
├── frontend/         React SPA (Vite + TypeScript + Tailwind + shadcn/ui)
│   ├── src/          Pages, components, API client, types
│   └── tests/
├── deploy/           Deploy script, systemd units, docker-compose.prod.yml
├── docs/             Architecture, operations, specs
└── .github/          CI workflows, PR template
```

## Key architectural decisions

Full decision records with context, alternatives, and rationale live in [docs/decisions/](decisions/). Summaries below.

### Modular monolith over microservices

Services share a PostgreSQL database but never import each other's code. Each has its own Dockerfile, dependencies, and tests. This gives service independence without the operational overhead of service mesh, API gateways, or distributed tracing — appropriate for a solo developer.

### PostgreSQL as the integration layer

The scraper writes to `products`, the backend reads from `products` and manages `watches`, `users`, `chat_sessions`. No message queue, no pub/sub, no event bus. At 20 users with a weekly-updated catalog, the database is the simplest reliable integration point.

### pgvector for RAG retrieval

Vector embeddings stored alongside relational data in the same PostgreSQL instance. Hybrid queries (vector similarity + SQL filters for category, price, country, availability) in one statement. No extra service, no vendor lock-in. See [ENGINEERING.md](ENGINEERING.md#ai--ml) for the full pipeline.

### Separate schemas per boundary

A product passes through three stages — scraping, storage, and API response — each with different requirements. Three separate schemas, one per boundary:

```text
SAQ.com HTML                    PostgreSQL                      JSON API
     │                               │                              │
     ▼                               ▼                              ▼
 ProductData                     Product                      ProductOut
 (dataclass)                  (SQLAlchemy)                    (Pydantic)
     │                               │                              │
scraper/src/products.py       core/db/models.py         backend/schemas/product.py
```

**`ProductData` — `@dataclass`**: The scraper parses messy HTML. A dataclass is a transparent container — it stores whatever you give it without fighting back. Validation happens in parser logic, not in the data structure.

**`Product` — SQLAlchemy model**: The ORM model is the single source of truth for the DB schema. Alembic generates migrations from it. Both services import it from `core/` — the scraper writes to it, the backend reads from it.

**`ProductOut` — Pydantic `BaseModel`**: Validates, coerces (`Decimal` → string, `datetime` → ISO 8601), and filters (drops `description`, `url`, `image` for legal reasons). FastAPI reads this schema for OpenAPI docs and response validation.

**Rule of thumb:** dataclass = trusted internal input; SQLAlchemy = persistence; Pydantic = external boundary.

### API contract excludes verbatim SAQ content

`ProductOut` omits `description`, `url`, and `image` to avoid legal risk (verbatim text and hotlinked assets). The data remains in the DB for internal use (embeddings, search).

### Auth model

JWT tokens issued via Telegram OAuth login. All API routes (except `/health`) require a valid JWT. The bot authenticates via a shared `BOT_SECRET` header. Invite codes gate new user registration. See [SECURITY.md](SECURITY.md) for the full auth model.

### Offset-based pagination

Simple, well-understood, sufficient for ~14k products. Cursor-based pagination would be needed at 100k+ rows or for real-time feeds.

### Stateless API

No in-memory state in the backend. Any request can hit any instance. This enables horizontal scaling (multiple uvicorn workers or containers) with zero code changes.

## Scaling path

| Scale | Bottleneck | Solution |
|-------|-----------|----------|
| 20 users | Nothing | Current setup |
| 200 users | Slow queries | Add DB indexes, connection pooling |
| 2,000 users | Repeated queries | Redis cache, read replica |
| 10,000+ users | Claude API latency | Async task queue, response caching |

The design principle: add infrastructure when a bottleneck is measured, not when it's imagined.

## Infrastructure

- **VPS**: Hetzner CX22, Debian 13 — managed in the [infra repo](https://github.com/vpatrin/infra)
- **Containers**: Docker Compose (dev + prod profiles)
- **Database**: PostgreSQL 16 + pgvector (shared instance, `saq_sommelier` database)
- **Reverse proxy**: Caddy (automatic HTTPS, managed in infra repo)
- **CI/CD**: GitHub Actions → GHCR → manual deploy via `deploy.sh`
- **Domain**: `coupette.club` (frontend SPA served by Caddy, API proxied to backend)

## Legal constraints

SAQ scraping follows a sitemap-first approach for legal defensibility:

- Only fetch URLs listed in SAQ's official sitemaps (declared in robots.txt)
- Rate limit: minimum 2 seconds between requests
- Transparent User-Agent identification
- Never expose verbatim SAQ descriptions through the API
- Never hotlink SAQ images
- Respect all Disallow rules in robots.txt

Scraper operations documented in [OPERATIONS.md](OPERATIONS.md).

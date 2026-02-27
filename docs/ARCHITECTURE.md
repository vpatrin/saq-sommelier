# Architecture

## Overview

SAQ Sommelier is a wine recommendation tool built on data from the SAQ (Societe des alcools du Quebec) catalog. It scrapes ~38k products, stores them in PostgreSQL, and serves them through a FastAPI API. A Telegram bot provides natural language recommendations powered by Claude.

Designed as a **modular monolith** for a solo developer serving ~20 users. Services are independently deployable containers that communicate through PostgreSQL — not by importing each other's code.

## System diagram

```
                          ┌─────────────────────┐
                          │      CLIENTS         │
                          │                      │
                          │  Telegram Bot (main)  │
                          │  React Dashboard (?)  │
                          └──────────┬───────────┘
                                     │
                                HTTPS (Caddy)
                                     │
                          ┌──────────▼───────────┐
                          │   BACKEND (FastAPI)   │
                          │                       │
                          │  /health              │
                          │  /products            │
                          │  /products/{sku}      │
                          │  /products/facets     │
                          │  /products/random     │
                          │  /watches             │
                          │  /recommend (Phase 6) │
                          │                       │
                          └──┬──────────────┬─────┘
                             │              │
                    ┌────────▼─────┐  ┌─────▼──────────┐
                    │  PostgreSQL  │  │  Claude API     │
                    │              │  │  (Haiku 4.5)    │
                    │  products    │  │                 │
                    │  watches     │  │  NL queries     │
                    │  stock_events│  │  Recommendations│
                    │  stores      │  └────────────────┘
                    └────────▲─────┘
                             │
                             │ writes
                             │
                    ┌────────┴────────────┐
                    │  SCRAPER            │
                    │                     │
                    │  Sitemap → Parser   │
                    │  → Upsert to DB     │
                    │                     │
                    │  Weekly cron         │
                    │  2s/req rate limit   │
                    │  ~38k products       │
                    └─────────────────────┘
```

## Data flow

| Path | Flow |
|------|------|
| **Write** | SAQ.com → Scraper → PostgreSQL |
| **Read** | Client → Caddy → FastAPI → PostgreSQL → Response |
| **AI** | Client → FastAPI → Claude API → Formatted response |

## Project structure

```
saq-sommelier/
├── backend/          FastAPI API (reads from DB)
│   ├── api/          HTTP endpoints (products, watches, health)
│   ├── repositories/ Database queries (SQLAlchemy)
│   ├── services/     Business logic + domain error translation
│   ├── schemas/      Pydantic request/response models (API contract)
│   ├── db.py         Session factory + get_db dependency
│   ├── app.py        App entry point + router registration
│   └── tests/
├── bot/              Telegram bot (calls backend API)
│   ├── bot/          Handlers, formatters, keyboards, API client
│   └── tests/
├── scraper/          Standalone scraper (writes to DB)
│   └── src/          Sitemap fetcher, HTML parser, DB upsert
├── core/             Core infrastructure (Poetry path dependency)
│   ├── db/           SQLAlchemy base, models, session factory
│   ├── config/       Pydantic Settings (DB connection)
│   └── logging.py    Loguru setup
├── deploy/           Systemd unit files for production scheduling
├── docs/             Architecture and findings
└── .github/          CI workflows
```

## Key architectural decisions

### Modular monolith over microservices

Services share a PostgreSQL database but never import each other's code. Each has its own Dockerfile, dependencies, and tests. This gives service independence without the operational overhead of service mesh, API gateways, or distributed tracing — appropriate for a solo developer.

### PostgreSQL as the integration layer

The scraper writes to `products`, the backend reads from `products` and manages `watches`. No message queue, no pub/sub, no event bus. At 20 users with a static catalog, the database is the simplest reliable integration point. A queue would add complexity without adding value.

### Separate schemas per boundary

A product passes through three stages — scraping, storage, and API response — each with different requirements. Three separate schemas, one per boundary:

```text
SAQ.com HTML                    PostgreSQL                      JSON API
     │                               │                              │
     ▼                               ▼                              ▼
 ProductData                     Product                    ProductResponse
 (dataclass)                  (SQLAlchemy)                    (Pydantic)
     │                               │                              │
scraper/src/products.py       core/db/models.py         backend/schemas/product.py
```

**`ProductData` — `@dataclass`**: The scraper parses messy HTML. A dataclass is a transparent container — it stores whatever you give it without fighting back. Validation happens in parser logic, not in the data structure. Pydantic here would require declaring every edge case upfront.

**`Product` — SQLAlchemy model**: The ORM model is the single source of truth for the DB schema. Alembic generates migrations from it. Both services import it from `core/` — the scraper writes to it, the backend reads from it.

**`ProductResponse` — Pydantic `BaseModel`**: Validates, coerces (`Decimal` → string, `datetime` → ISO 8601), and filters (drops `description`, `url`, `image` for legal reasons). FastAPI reads this schema for OpenAPI docs and response validation.

Without separation: adding a scraper debug field leaks into the API; removing an API field for legal reasons breaks the scraper. With separation, each boundary evolves independently — the database is the only shared contract.

**Rule of thumb:** dataclass = trusted internal input; SQLAlchemy = persistence; Pydantic = external boundary.

### API contract excludes verbatim SAQ content

`ProductResponse` omits `description`, `url`, and `image` to avoid legal risk (verbatim text and hotlinked assets). The data remains in the DB for internal use. These fields will be re-added when paraphrasing (Claude) and image proxying are implemented.

### Offset-based pagination

Simple, well-understood, sufficient for 38k products. Cursor-based pagination would be needed at 100k+ rows or for real-time feeds. Not worth the complexity now.

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

- **Containers**: Docker Compose (`make run` for full dev stack, `make run-db` for bare-metal dev)
- **Database**: PostgreSQL 16 (shared instance, `saq_sommelier` database)
- **CI**: GitHub Actions (lint + test per service, summary gates)

## Legal constraints

SAQ scraping follows a sitemap-first approach for legal defensibility:

- Only fetch URLs listed in SAQ's official sitemaps (declared in robots.txt)
- Rate limit: minimum 2 seconds between requests
- Transparent User-Agent identification
- Never expose verbatim SAQ descriptions through the API
- Never hotlink SAQ images
- Respect all Disallow rules in robots.txt

Scraper operations documented in [OPERATIONS.md](OPERATIONS.md).

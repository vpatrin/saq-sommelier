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
                    ┌────────▼────┐   ┌─────▼──────────┐
                    │ PostgreSQL  │   │  Claude API     │
                    │             │   │  (Haiku 3.5)    │
                    │  products   │   │                 │
                    │  watches    │   │  NL queries     │
                    │             │   │  Recommendations │
                    └────────▲────┘   └────────────────┘
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
├── scripts/          Exploration tools (not deployed)
├── docs/             Architecture and findings
└── .github/          CI workflows
```

## Key architectural decisions

### Modular monolith over microservices

Services share a PostgreSQL database but never import each other's code. Each has its own Dockerfile, dependencies, and tests. This gives service independence without the operational overhead of service mesh, API gateways, or distributed tracing — appropriate for a solo developer.

### PostgreSQL as the integration layer

The scraper writes to `products`, the backend reads from `products` and manages `watches`. No message queue, no pub/sub, no event bus. At 20 users with a static catalog, the database is the simplest reliable integration point. A queue would add complexity without adding value.

### Separate schemas per boundary

- `ProductData` (scraper) — raw parsed data entering the system
- `Product` (core) — SQLAlchemy model, single source of truth for DB schema
- `ProductResponse` (backend) — curated API output, excludes sensitive fields

These overlap but are intentionally separate. The scraper can change its parsing without breaking the API contract, and vice versa.

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

- **Host**: Hetzner CX22 (4GB RAM, 40GB SSD, Debian 13)
- **Reverse proxy**: Caddy (SSL + routing via victorpatrin.dev subdomains)
- **Containers**: Docker Compose (`make run` for full dev stack, `make run-db` for bare-metal dev)
- **Database**: PostgreSQL 16 (shared instance, `wine_sommelier` database)
- **CI**: GitHub Actions (lint + test per service, summary gates)

## Legal constraints

SAQ scraping follows a sitemap-first approach for legal defensibility:

- Only fetch URLs listed in SAQ's official sitemaps (declared in robots.txt)
- Rate limit: minimum 2 seconds between requests
- Transparent User-Agent identification
- Never expose verbatim SAQ descriptions through the API
- Never hotlink SAQ images
- Respect all Disallow rules in robots.txt

Full scraping findings documented in [scripts/FINDINGS.md](../scripts/FINDINGS.md).

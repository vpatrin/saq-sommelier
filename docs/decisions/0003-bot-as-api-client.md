# ADR 0003: Bot Communicates via Backend API, Not Direct DB

**Date:** 2026-02-18
**Status:** Accepted

## Context

The Telegram bot needs product data, watch management, and notification delivery. Two approaches: call the backend API over HTTP, or import `core/` and query PostgreSQL directly (like the scraper does).

## Options considered

1. **Direct DB access** — bot imports `core/`, runs SQLAlchemy queries. Same pattern as the scraper.
2. **HTTP API client** — bot calls the backend's REST endpoints. Backend owns all business logic.

## Decision

Option 2. The bot is a thin client that calls the backend API via `httpx`. It authenticates with a shared `X-Bot-Secret` header.

## Rationale

- **The bot is a presentation layer.** It formats responses for Telegram — it shouldn't own business logic like watch deduplication, notification batching, or product filtering. The backend already has that logic for the web app.
- **The scraper is different.** The scraper writes raw data to the database — it's a data pipeline, not a consumer of business logic. Direct DB access is appropriate there.
- **Single source of truth for behavior.** If both bot and web app call the same API, filtering rules, pagination, and access control are consistent. With direct DB, the bot would need its own query logic that could drift from the backend's.
- **Testability.** Bot tests mock HTTP responses, not database sessions. Faster, simpler, no SQLAlchemy fixtures.

## Consequences

- Bot depends on backend being up. If the backend is down, the bot can't serve product data or manage watches. Acceptable — the backend is the core service.
- Adds network hop latency (~1ms on the same Docker network). Negligible.
- Bot needs `BACKEND_URL` and `BOT_SECRET` config. The scraper doesn't need either — it writes directly.

# ADR 0002: Sitemap-First Scraping with Adobe API Enrichment

**Date:** 2026-02-13 (sitemap scraping) · Updated 2026-03-05 (Adobe API pivot)
**Status:** Accepted

## Context

Coupette needs wine catalog data from the SAQ (Société des alcools du Québec). Web scraping is in a legal grey zone in Canada. We need a strategy that is legally defensible, technically reliable, and provides enough product detail for recommendations.

Started with **pure sitemap + HTML scraping** (Feb 2026) — legally conservative (only fetching URLs SAQ publishes in `robots.txt`), but brittle. SAQ's markup varied across pages, some attributes were missing from HTML, and in-store availability only rendered via JavaScript.

While debugging availability in the browser's network console, discovered SAQ's frontend calls an **Adobe Live Search GraphQL endpoint** (`livesearch.adobe.io`) — public, no auth, structured data. This discovery opened a hybrid approach.

## Options considered

1. **Pure HTML scraping** — sitemap URLs → parse HTML for all product data. Legally conservative but brittle (markup changes break extraction, JS-rendered data inaccessible).
2. **Adobe API only** — skip sitemap, query Adobe for everything. Structured data but no legal basis (no `robots.txt` reference), and API could change without notice.
3. **Hybrid: sitemap for discovery, Adobe API for enrichment** — sitemap provides the legal basis and product catalog; Adobe API fills in tasting notes, grape varieties, and store-level availability.

## Decision

Option 3: hybrid approach with staged commands, each independently runnable:

1. `scrape-products` — sitemap → HTML → base product data → DB
2. `scrape-enrich` — Adobe API → wine attributes, tasting notes → DB
3. `scrape-availability` — Adobe API → store-level stock status → DB
4. `embed-sync` — product text → OpenAI embeddings → pgvector
5. `scrape-stores` — SAQ store directory → DB

One-shot batch job model: scraper runs via systemd timer (weekly for catalog, daily for availability), exits with named codes (`EXIT_OK`/`EXIT_PARTIAL`/`EXIT_FATAL`). Not a long-running daemon — each run is isolated, idempotent, and observable via exit status.

## Rationale

- **Legal defensibility.** SAQ's `robots.txt` explicitly lists sitemap URLs. Fetching only those URLs is the most conservative position. Adobe API is a public endpoint called by SAQ's own frontend — no auth bypass, no rate limit evasion.
- **Reliability.** Structured API responses don't break when SAQ redesigns their HTML. The sitemap still provides the full catalog (~38k SKUs, filtered to ~14k wine post-scrape).
- **Staged pipeline.** Each command can fail independently — enrichment failure doesn't block base scraping. Each stage is resumable and idempotent.
- **Batch over daemon.** A one-shot job with systemd `Persistent=true` is simpler to monitor (exit codes), debug (run manually), and schedule than a long-running process with internal timers.
- **Ethical self-constraints.** Rate limit (min 2s between requests), transparent User-Agent, never copy SAQ descriptions verbatim, always attribute SAQ as data source, respect all `robots.txt` Disallow rules, abort if `robots.txt` is unreachable (fail-safe).

## Consequences

- Two external dependencies (SAQ website + Adobe API) instead of one. If Adobe changes their API, enrichment breaks but base scraping still works.
- Wine-only filtering happens post-scrape — the sitemap contains all categories (spirits, beer, cider).
- Five CLI commands instead of one. `scrape-all` runs the first four in order; `embed-sync` is intentionally separate (slower, costs money, only needed after content changes).

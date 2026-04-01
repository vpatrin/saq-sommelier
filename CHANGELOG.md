# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Public landing page — bilingual hero, RAG pipeline walkthrough, changelog timeline, open source section with live GitHub commits

### Changed

- Search, watchlist, and stores pages restyled — horizontal filter bar on search, availability dots on watchlist, card layout on stores, empty states on all three
- Login route moved to `/login`; `/` now serves the public landing page
- "Watchlist" renamed to "Favoris" throughout the French UI
- Chat UI restyle — Claude-style message bubbles, inline message actions (copy, thumbs, regenerate), session title bar with rename/delete, scroll-to-bottom button
- Wine cards restyled — dot-color category indicator, grapes list with expand/collapse, cleaner availability display

## [1.5.2] - 2026-03-24

### Added

- Bilingual web app — French (default) and English, with language switcher in sidebar

## [1.5.1] - 2026-03-21

### Added

- Prometheus metrics endpoint for API observability (#497)

### Fixed

- Facets endpoint runs 5 DB queries concurrently via `asyncio.gather` instead of sequentially — ~3.5× faster (p95: 910ms → ~250ms expected) (#508)
- Explicit connection pool config (`pool_size=10, max_overflow=10, pool_timeout=5s`) to prevent pool exhaustion from concurrent facets queries (#508)
- Frontend deploy: build in CI runner, clear old assets before SCP (#487, #488)
- Docker healthcheck in deploy script (#496)

### Changed

- Docker Compose refactored into base/prod/dev overlay layers (#491)
- CD pipeline supports manual infra deploys via workflow_dispatch (#500)

## [1.5.0] - 2026-03-19

### Added

- Conversation starters — 4 clickable prompts on the empty chat state that auto-submit on click (#474)
- Chat API — session-based chat endpoints wrapping the recommendation pipeline (`/api/chat/sessions/*`) (#425)
- Chat UI — sommelier conversation page with message input, response display, and session persistence (#426)
- Session history sidebar — list, resume, rename, and delete past chat sessions
- Three-way intent routing — chat queries are classified as recommendation, wine knowledge, or off-topic; wine knowledge questions get conversational answers instead of product cards (#473)

### Changed

- Deploy is now fully automated — tag push triggers CD pipeline (build → scan → deploy via SSH) (#482)
- Production secrets encrypted with sops + age, decrypted at deploy time (#482)
- Wine cards in chat now show grape, vintage, availability, and bottle size (#440)
- Chat recommendations now use multi-turn context — previous wines are excluded and curation references prior conversation (#428)
- REST API hygiene — pagination uses `limit`/`offset` instead of `page`/`per_page`, verb-based URLs replaced with PATCH (#431)

### Fixed

- Products no longer show stale "Online" availability when absent from Adobe results (#449)
- Recommendation pipeline now fully async — intent parsing, embeddings, and curation no longer block the event loop
- DB session lifecycle cleanup — removed redundant `commit()` and `refresh()` calls, centralized client singletons

## [1.4.0] - 2026-03-12

### Added

- React frontend with Telegram OAuth login, JWT session persistence, and invite code support
- Watch dashboard — view watched wines with availability status, remove watches (#385)
- Nearby stores page — browser geolocation, store cards with distance (#387)
- Store picker — saved stores page, save/unsave toggle on nearby stores (#388)
- Enriched watch cards — SAQ product link, smart origin display, store availability cross-referenced with saved stores (#412)
- Telegram onboarding card on dashboard — deep link to @CoupetteBot (#412)
- Product search page with category, country, price, and availability filters (#386)
- Sidebar navigation (AppShell) — persistent across all authenticated pages
- "In my stores" availability filter — cross-references saved stores with product stock
- Availability status on search results — online, in-store with store names, clickable expand
- Automatic logout on expired JWT (401 interceptor)

### Changed

- Invite links (`/invite/:code`) replace manual code input — cleaner onboarding UX (#408)
- Dashboard replaced by search page as default post-login destination
- Store preferences moved from `/users/{id}/stores` to `/stores/preferences` — single router, JWT-aware

### Removed

- Dashboard page (functionality moved to sidebar + search)

### Fixed

- Facet filters (regions, grapes, price range) now respect availability filters
- Systemd timers use prod Docker Compose override so scraper/availability run from GHCR images instead of attempting local builds

### Security

- API endpoints now derive user_id from JWT — prevents client-supplied impersonation (#401)

## [1.3.1] - 2026-03-10

### Fixed

- Alembic migration fails when DB password contains special characters — configparser `%` escaping (#378)
- Deploy script pgvector extension creation uses superuser to avoid permission error (#378)

## [1.3.0] - 2026-03-10

### Added

- Wine scope default — API endpoints now return wine-only results by default; use `scope=all` for full catalog (#285)
- Daily availability refresh via Adobe Live Search — replaces planned `--check-watches` (#289)
- Intent parser — Claude Haiku extracts structured filters (category, price, country) from natural language wine queries (#155)
- `POST /api/recommendations` — natural language wine recommendations via intent parsing + embedding similarity search (#309, #310, #311)
- `/recommend` bot command — ask for wine recommendations in natural language via Telegram (#156)
- Per-product reasoning and summary in recommendations — Claude Haiku explains why each wine was selected (#328)
- Explicit availability filters on recommendations — `available_online` and `in_store` on request body, decoupled from intent parsing (#345)
- Telegram Login Widget authentication — `POST /api/auth/telegram` verifies HMAC, upserts user, returns JWT (#353)
- JWT route guards — all API routes require authentication except `/health` and `/api/auth` (#356)
- Invite code access gate — new users must present a single-use invite code at first login (#357)
- Admin bootstrap — `make create-admin` seeds admin user from `ADMIN_TELEGRAM_ID`, backend startup verifies admin exists
- Admin user management — `GET /api/admin/users` lists all users, `POST /api/admin/users/{id}/deactivate` deactivates non-admin users

### Fixed

- Bot blocked by JWT route guards — unified auth accepts either JWT or bot secret (#371)
- Deactivated users could access protected routes via valid JWT — `verify_auth` now checks `is_active`

### Changed

- Bot access gate now checks user registration in database instead of env var allowlist (#358)
- Improved recommendation diversity and relevance (grape-aware retrieval, accumulating reranker)
- Non-wine graceful decline — asking for beer, spirits, etc. returns a bilingual "I'm a wine assistant" message instead of unrelated results
- Availability filter — recommendations now exclude products not available online
- Enriched `/recommend` cards — now show grape, region/country (deduplicated), taste tag, vintage, and availability status
- `/recommend` defaults to wine categories when intent parser extracts no category filter

### Security

- URL-encode database password to handle special characters in connection strings (#313)
- Backend refuses to start in production without BOT_SECRET configured (#313)

### Removed

- `/new` and `/random` bot commands — browse UX belongs in web frontend, bot focuses on alerts and recommendations

## [1.2.0] - 2026-03-03

### Added

- SAQ URL paste — paste a product link in chat to get a one-tap Watch / Skip prompt (#273)
- Deeplink support — `t.me/bot?start=watch_{sku}` triggers the watch flow directly, enabling Chrome extension integration (#273)
- Per-product store availability checker — daily alerts for watched wines at preferred stores (#149)
- `/mystores` bot command — GPS-based store picker with inline toggle keyboard (#233)
- `/stores/nearby` endpoint — returns nearest SAQ stores sorted by GPS distance (#232)
- User store preferences CRUD — `/users/{id}/stores` add, list, and remove preferred stores (#232)
- Store directory — SAQ physical store locations scraped and stored on first scraper run (#128)
- Programmatic robots.txt compliance — scraper filters disallowed URLs and aborts if robots.txt is unreachable (#196)
- Paginated results with prev/next navigation buttons (#167)
- Out-of-stock notifications — watched products now alert users when availability drops (#212)
- Delist notifications — users watching a product are alerted when SAQ removes it from the catalog (#243)

### Security

- Bot→backend notification endpoints protected with `X-Bot-Secret` shared secret; no-op when unconfigured (dev) (#276)

### Changed

- Watches auto-removed when a delisted product is acked — no manual cleanup needed, message explains why (#277)
- `/alerts` shows inline remove buttons per wine — tap to unwatch without typing `/unwatch` (#240)
- `/watch` and `/unwatch` now show the updated watch list keyboard directly, with no separate confirmation message (#240)
- Group stock notifications by product — one message per wine listing all affected stores, with online availability hint (#256)
- Targeted store availability fetch — checks only preferred stores via lat/lng proximity instead of paginating all ~400 stores (#254)
- HTTP 404s logged as warnings instead of errors, counted separately in run summary (#197)
- Flat wine type filter keyboard (Rouge/Blanc/Rosé/Bulles) replaces two-level family hierarchy (#167)
- Skip ~1,500 non-product URLs (recipes, accessories) during scrape, saving ~50 min per run (#188)

### Removed

- `currency` field dropped from product API responses — was always `"CAD"`, never meaningful (#223)

### Fixed

- Weekly scraper no longer emits stock events from CDN-cached HTML, eliminating false restock/destock notifications (#241)
- Prevent false destock alerts when GraphQL omits `stock_status` — field now defaults to unknown instead of `OUT_OF_STOCK` (#248)
- Fix first-run store event flood — first availability check now establishes baseline without emitting spurious events (#149)
- Availability checker now exits with EXIT_FATAL when GraphQL resolves 0 products instead of silently reporting success (#244)
- Parse prices with thousands separator (e.g. $1,624.75) instead of silently dropping them (#191)
- Fix encoding mojibake on product names and categories with accented characters (#191)
- DB errors in scraper and bot now logged with full context — previously swallowed silently (#249)
- Unhandled bot handler exceptions now logged via loguru instead of being silently discarded (#249)
- Loguru format string `%d/%d` in watch ack warning now correctly substituted (#249)

## [1.1.0] - 2026-02-20

### Security
- Telegram user allowlist and per-user rate limiting (#178)

### Added
- Persistent reply keyboard with New wines, Random, My alerts, and Help buttons (#164)
- Redesigned /start and /help text with grouped commands and project branding (#164)

### Changed
- Show updated watch list after /watch and /unwatch commands (#183)
- Disable Telegram link preview for multi-result messages, keep preview for single results (#165)

### Fixed
- Restrict category filters to wine-only categories (#166)

## [1.0.0] - 2026-02-19

### Added
- Sitemap-based scraper with incremental updates, delist detection, and run summaries
- Product catalog API — list, detail, search, filtering, sorting, random pick
- Watches CRUD — create/delete watches, check restock status
- Catalog facets endpoint for dynamic filter options
- Telegram bot with `/new`, `/random`, `/watch`, `/unwatch`, `/alerts` commands
- Inline keyboard filters for category, country, and price range
- Post-scrape restock notifications for watched products
- Docker Compose deployment with Caddy reverse proxy
- CI pipeline with per-service linting, testing, and coverage thresholds

[Unreleased]: https://github.com/vpatrin/coupette/compare/v1.5.2...HEAD
[1.5.2]: https://github.com/vpatrin/coupette/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/vpatrin/coupette/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/vpatrin/coupette/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/vpatrin/coupette/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/vpatrin/coupette/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/vpatrin/coupette/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/vpatrin/coupette/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/vpatrin/coupette/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/vpatrin/coupette/releases/tag/v1.0.0

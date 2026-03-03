# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/vpatrin/saq-sommelier/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/vpatrin/saq-sommelier/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/vpatrin/saq-sommelier/releases/tag/v1.0.0

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Parse prices with thousands separator (e.g. $1,624.75) instead of silently dropping them (#191)
- Fix encoding mojibake on product names and categories with accented characters (#191)

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

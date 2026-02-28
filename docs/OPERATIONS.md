# Operations

Production operations for the scraper and database migrations.

---

## Scraper

### How it works

The scraper is a one-shot batch job, not a long-running service. Each run:

1. Fetches the SAQ sitemap index and all sub-sitemaps
2. Validates URLs against SAQ's `robots.txt` via `urllib.robotparser` — disallowed URLs are skipped, and the run aborts if `robots.txt` is unreachable
3. Filters non-product URLs (only numeric SKU paths are scraped)
4. Compares sitemap `lastmod` dates against DB `updated_at` (incremental — skips unchanged products)
5. Scrapes only new/updated product pages, upserts to PostgreSQL
6. Emits stock events when availability changes (restock or destock) for the notification pipeline
7. Detects delisted products (in DB but not in sitemap) and marks them with `delisted_at`
8. Relists products that reappear in the sitemap
9. Exits with a named status code: `EXIT_SUCCESS` (0), `EXIT_PARTIAL` (1), `EXIT_FAILURE` (2)

A typical incremental run scrapes ~50-200 products instead of the full ~38k catalog.

### Store directory bootstrap

The scraper automatically populates the `stores` table on first run if it is empty. No separate command is needed.

SAQ stores are physical locations — they rarely change. If a new store opens or closes, clear the `stores` table and run the scraper; the bootstrap will re-fetch all 401 stores before starting the product scrape.

### Running manually

See [DEVELOPMENT.md](DEVELOPMENT.md#working-on-the-scraper) for local dev usage (`make dev-scraper`, `make reset-db`).

### Production scheduling

The scraper runs weekly via a **systemd timer** on the VPS. Systemd handles scheduling, logging (journald), and exit code tracking.

#### Unit files

Source files: [`deploy/saq-scraper.service`](../deploy/saq-scraper.service) and [`deploy/saq-scraper.timer`](../deploy/saq-scraper.timer).

The service file assumes `WorkingDirectory=/opt/saq-sommelier`. If your repo lives elsewhere, either symlink it:

```bash
sudo ln -s /path/to/your/saq-sommelier /opt/saq-sommelier
```

Or edit `WorkingDirectory` in the installed service file after copying.

#### Installation

```bash
sudo cp deploy/saq-scraper.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now saq-scraper.timer
```

`Persistent=true` in the timer means if the VPS was off during the scheduled time, it runs on next boot. Only the timer is enabled — it triggers the oneshot service on schedule.

#### Checking status

```bash
systemctl status saq-scraper.timer     # next/last run times
systemctl list-timers                  # all active timers
journalctl -u saq-scraper.service      # all scraper logs
journalctl -u saq-scraper.service -n 50 --no-pager   # last 50 lines
```

#### Manual trigger

```bash
sudo systemctl start saq-scraper.service
```

### Failure recovery

The scraper is **idempotent**. If a run crashes at product 1000 out of 38000:

- The 999 already-saved products have a fresh `updated_at`
- Next run's incremental filter skips them automatically
- Only the remaining products get scraped

No manual intervention needed — the next scheduled run picks up where it left off.

Delist detection is best-effort. If it fails, it logs an error and the next run catches up.

**No auto-retry by design.** If SAQ is down, retrying every 5 minutes for a week wastes resources and isn't ethical scraping. Weekly cadence is sufficient for a ~20-user app.

### Exit codes

Defined as named constants in `scraper/src/constants.py`.

| Code | Constant | Meaning | Action needed |
| ---- | -------- | ------- | ------------- |
| `0` | `EXIT_SUCCESS` | Clean run | None |
| `1` | `EXIT_PARTIAL` | Partial failure (some products saved, some failed) | Check logs, usually transient |
| `2` | `EXIT_FAILURE` | Total failure (nothing saved) | Investigate — likely SAQ down or DB unreachable |

### Robots.txt compliance

The scraper programmatically enforces SAQ's `robots.txt` rules:

- On startup, fetches and parses `https://www.saq.com/robots.txt` via `urllib.robotparser`
- Each URL is checked with `can_fetch()` before scraping — disallowed paths are skipped with a warning
- If `robots.txt` is unreachable, the run **aborts** rather than scraping blind — fail-safe over fail-open

---

## Availability checker

Daily job that checks online and in-store availability for watched SKUs. Separate from the weekly product scrape — runs as `python -m src --check-watches`.

### How it works

1. Loads all watched SKUs (`SELECT DISTINCT sku FROM watches`)
2. Batch-resolves Magento IDs + `stock_status` via GraphQL (batches of 20)
3. For each SKU: fetches per-store quantities via AJAX, diffs against previous snapshot
4. Emits `StockEvent` rows on transitions (online restock/destock, per-store restock/destock)
5. Upserts `product_availability` with the new snapshot
6. Purges stock events older than 7 days

Exits immediately if no watched SKUs exist. See [specs/STORE_AVAILABILITY.md](specs/STORE_AVAILABILITY.md) for API details and routing logic.

### Scheduling and operations

Runs daily at 2am via systemd timer, one hour before the DB backup (3am).

Source files: [`deploy/saq-watches.service`](../deploy/saq-watches.service) and [`deploy/saq-watches.timer`](../deploy/saq-watches.timer).

```bash
# Install
sudo cp deploy/saq-watches.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now saq-watches.timer

# Status and logs
systemctl status saq-watches.timer
journalctl -u saq-watches.service -n 50 --no-pager

# Manual trigger
sudo systemctl start saq-watches.service
```

### Running locally

```bash
cd scraper && poetry run python -m src --check-watches
```

Requires a running PostgreSQL with at least one watch in the `watches` table. Without watched SKUs, it exits immediately.

### Resilience

The checker is **idempotent**. If it crashes mid-run, the next run re-diffs from the last saved snapshot. Worst case: a missed transition gets detected 24 hours late.

Same no-auto-retry policy as the scraper — if SAQ is down, the next daily run catches up.

### Runtime estimate

With targeted store fetching (lat/lng): ~50 SKUs × 3 preferred stores = 150 AJAX requests + 3 GraphQL calls at 2s rate limit = **~5 minutes**.

Without targeting (full pagination): ~50 SKUs × ~11 pages = 550 AJAX requests = **~18 minutes**.

---

## Migrations

### Applying migrations

```bash
make migrate                           # apply all pending migrations
cd core && poetry run alembic current  # check current version
cd core && poetry run alembic history  # show migration history
```

### Forward-only in production

Never run `downgrade()` on production. If a migration adds a column and populates it with data, downgrading drops that column and the data. Write a new migration to fix mistakes instead.

### Pre-production squash

Before the first production deployment, squash all dev migrations into one clean `initial`:

```bash
make squash
# Then hand-add CREATE EXTENSION to the generated file
make reset-db  # verify it works
```

After production exists, never squash — migrations become the permanent history.

### Backward-compatible deploys

If old code and new code run simultaneously during a rolling deploy:

1. Add columns as **nullable** (old code ignores them)
2. Backfill data in a follow-up migration
3. Add NOT NULL constraints only after backfill is complete

Never rename or drop a column that old code still reads.

See [DEVELOPMENT.md](DEVELOPMENT.md#migrations) for the local development migration workflow.

# Scraper Operations

## How it works

The scraper is a one-shot batch job, not a long-running service. Each run:

1. Fetches the SAQ sitemap index and all sub-sitemaps
2. Compares sitemap `lastmod` dates against DB `updated_at` (incremental — skips unchanged products)
3. Scrapes only new/updated product pages, upserts to PostgreSQL
4. Detects delisted products (in DB but not in sitemap) and marks them with `delisted_at`
5. Relists products that reappear in the sitemap
6. Exits with a status code: `0` (clean), `1` (partial failure), `2` (total failure)

A typical incremental run scrapes ~50-200 products instead of the full ~38k catalog.

## Running manually

See [DEVELOPMENT.md](DEVELOPMENT.md#working-on-the-scraper) for local dev usage (`make scrape`, `make reset-db`).

## Production scheduling

The scraper runs weekly via a **systemd timer** on the VPS. Systemd handles scheduling, logging (journald), and exit code tracking.

### Unit files

Source files: [`deploy/saq-scraper.service`](../deploy/saq-scraper.service) and [`deploy/saq-scraper.timer`](../deploy/saq-scraper.timer).

Copy to the VPS:

```bash
sudo cp deploy/saq-scraper.{service,timer} /etc/systemd/system/
```

`Persistent=true` in the timer means if the VPS was off during the scheduled time, it runs on next boot.

### Setup

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now saq-scraper.timer
```

### Checking status

```bash
systemctl status saq-scraper.timer     # next/last run times
systemctl list-timers                  # all active timers
journalctl -u saq-scraper.service      # all scraper logs
journalctl -u saq-scraper.service -n 50 --no-pager   # last 50 lines
```

### Manual trigger

```bash
sudo systemctl start saq-scraper.service
```

## Failure recovery

The scraper is **idempotent**. If a run crashes at product 1000 out of 38000:

- The 999 already-saved products have a fresh `updated_at`
- Next run's incremental filter skips them automatically
- Only the remaining products get scraped

No manual intervention needed — the next scheduled run picks up where it left off.

Delist detection is best-effort. If it fails, it logs an error and the next run catches up.

**No auto-retry by design.** If SAQ is down, retrying every 5 minutes for a week wastes resources and isn't ethical scraping. Weekly cadence is sufficient for a ~20-user app.

## Exit codes

| Code | Meaning | Action needed |
|------|---------|---------------|
| `0` | Clean run | None |
| `1` | Partial failure (some products saved, some failed) | Check logs, usually transient |
| `2` | Total failure (nothing saved) | Investigate — likely SAQ down or DB unreachable |

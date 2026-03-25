# Development & Operations

Cold-start guide + production ops. If you're back after months away, start here.

VPS-level infrastructure (firewall, SSH, TLS, networking) lives in the [infra repo](https://github.com/vpatrin/infra/blob/main/docs/INFRASTRUCTURE.md).

---

## Getting running

Prerequisites: Python 3.12+, [Poetry](https://python-poetry.org/docs/#installation), Node.js 24+, [Yarn](https://classic.yarnpkg.com/), Docker.

```bash
make install              # Python + frontend deps
cp .env.example .env      # fill in values — the file documents itself
make run-db               # PostgreSQL on localhost:5432
make migrate              # create tables
make create-admin         # seed admin user (backend won't start without it)
make dev-scraper          # populate DB (~14k products)
make dev-backend          # API on localhost:8001
make dev-frontend         # SPA on localhost:5173
```

Or skip Poetry and run everything in Docker: `make run` (see `make help` for all targets).

Frontend always runs bare-metal (`yarn dev`) — hot reload matters.

## How the pieces connect

Each service is a separate Poetry project with its own Dockerfile. They share a PostgreSQL database and a `core/` package (models, Alembic, settings).

- **Backend** (FastAPI) — API on `:8001`, needs `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` for AI features
- **Bot** (python-telegram-bot) — polls Telegram in dev, calls backend API. Needs `TELEGRAM_BOT_TOKEN`
- **Scraper** — one-shot batch job, not a service. See [Scraper](#scraper)
- **Frontend** (React/Vite) — SPA on `:5173`, proxies to backend

All env vars are in `.env.example` with descriptions.

## Infra coupling

This repo and [`empire/infra`](https://github.com/vpatrin/infra) share a VPS (Hetzner CX22, Debian 13). They're coupled through:

- **Docker network**: `internal` (external, defined in infra's compose). All containers communicate by name.
- **Caddy routing** (infra's `services/caddy/Caddyfile`): `coupette.club/api/*` → `coupette-backend:8001`, `coupette.club/*` → static SPA from `/srv/coupette`
- **shared-postgres**: container defined in infra, used by coupette services

| | coupette/ | infra/ |
| --- | --------- | ------ |
| **Owns** | App containers, docker-compose.yml, CI, Alembic, deploy | Caddy, DNS, shared-postgres, Docker network, backups |
| **Deploys** | Build → GHCR → restart app containers | `git pull && docker compose up -d` |

**Cross-repo changes:** new route/subdomain → Caddyfile PR in infra. Container name or port change → update both compose files. New systemd timer → infra owns the timer inventory.

## Testing

```bash
make test          # all Python services (mocked DB, no live deps)
make test-backend  # single service
make coverage      # with badges
make lint          # ruff + eslint + typecheck
make format        # ruff + prettier
```

---

## Deploy

Two deploy paths via [cd.yml](../.github/workflows/cd.yml):

### Feature release (tag push)

For user-facing changes. Tag on main, push the tag.

```bash
git tag -a v1.6.0 -m "v1.6.0"
git push origin main --tags
```

**Flow:** tag push → build + scan + push to GHCR → GitHub Release (from CHANGELOG) → deploy to VPS

Tags are semver, reflect user-facing releases only. Internal changes (CI, observability, infra) don't get tags.

### Infra deploy (workflow dispatch)

For CI/CD, observability, deploy script, or config changes that don't affect users.

```bash
gh workflow run CD -f commit=<SHA>
```

**Flow:** dispatch → build from commit + push to GHCR (tagged `sha-<SHA>`) → deploy to VPS (no GitHub Release)

### What the deploy does

`deploy_backend.sh`: decrypt secrets → pull GHCR images → sync systemd units → migrate → bootstrap admin → restart → health check

Frontend: `yarn build` with version as `VITE_APP_VERSION`, SCP to `/srv/coupette`

### Verify

```bash
curl -s localhost:8001/health     # backend responds
# message the bot on Telegram    # bot responds
systemctl status coupette-scraper.timer       # timer active, next run scheduled
systemctl status coupette-availability.timer  # timer active, next run scheduled
```

### Rollback

```bash
# Tag release — redeploy previous tag (images already in GHCR)
cd /home/deploy/coupette && git checkout vPREVIOUS && IMAGE_TAG=vPREVIOUS SOPS_AGE_KEY=... ./deploy/deploy_backend.sh

# Dispatch deploy — redeploy previous commit
gh workflow run CD -f commit=<previous-SHA>
```

Migrations are forward-only — never run `downgrade()` in production. See [Migrations](#migrations).

---

## Scraper

The scraper is a one-shot batch job, not a long-running service. Each run:

1. Fetches the SAQ sitemap index and all sub-sitemaps
2. Validates URLs against SAQ's `robots.txt` via `urllib.robotparser` — disallowed URLs are skipped, and the run aborts if `robots.txt` is unreachable
3. Filters non-product URLs (only numeric SKU paths are scraped)
4. Compares sitemap `lastmod` dates against DB `updated_at` (incremental — skips unchanged products)
5. Scrapes only new/updated product pages, upserts to PostgreSQL
6. Detects delisted products (in DB but not in sitemap) and marks them with `delisted_at`
7. Relists products that reappear in the sitemap
8. Exits with a named status code: `EXIT_OK` (0), `EXIT_PARTIAL` (1), `EXIT_FATAL` (2)

A typical incremental run scrapes ~50-200 products instead of the full ~38k catalog.

### Store directory

Store population is separate from the weekly product scrape:

```bash
docker compose run --rm scraper python -m scraper stores
```

SAQ stores rarely change. Run on first deploy and again whenever a store opens or closes. Upsert is idempotent.

### Production scheduling

Weekly via **systemd timer**. Source files: [`deploy/systemd/coupette-scraper.service`](../deploy/systemd/coupette-scraper.service) and [`deploy/systemd/coupette-scraper.timer`](../deploy/systemd/coupette-scraper.timer).

```bash
# Install
sudo cp deploy/systemd/coupette-scraper.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coupette-scraper.timer

# Status
systemctl status coupette-scraper.timer
journalctl -u coupette-scraper.service -n 50 --no-pager

# Manual trigger
sudo systemctl start coupette-scraper.service
```

`Persistent=true` means if the VPS was off during the scheduled time, it runs on next boot.

The service assumes `WorkingDirectory=/home/deploy/coupette`.

### Failure recovery

The scraper is **idempotent**. If a run crashes at product 1000/38000, the next run's incremental filter skips already-saved products and picks up the rest.

**No auto-retry by design.** Weekly cadence is sufficient — retrying every 5 minutes when SAQ is down wastes resources and isn't ethical scraping.

### Exit codes

Defined in `scraper/src/constants.py`.

| Code | Constant | Meaning | Action |
| ---- | -------- | ------- | ------ |
| `0` | `EXIT_OK` | Clean run | None |
| `1` | `EXIT_PARTIAL` | Some products failed | Check logs, usually transient |
| `2` | `EXIT_FATAL` | Nothing saved | Investigate — SAQ down or DB unreachable |

### Robots.txt compliance

The scraper programmatically enforces SAQ's `robots.txt`:

- Fetches and parses `robots.txt` on startup via `urllib.robotparser`
- Each URL checked with `can_fetch()` — disallowed paths skipped with warning
- If `robots.txt` is unreachable, the run **aborts** (fail-safe over fail-open)

---

## Availability checker

Daily job that refreshes online and in-store availability from Adobe Live Search, detects transitions for watched products, and emits `StockEvent` alerts. Runs as `python -m scraper availability`.

See [specs/DATA_PIPELINE.md](specs/DATA_PIPELINE.md) § Availability Check for full architecture.

### How it works

1. Queries Adobe `inStock=true` (~4k products) → `online_availability` + `store_availability`
2. Queries Adobe Montreal stores `in` filter (~9.5k products) → En succursale availability, deduped by SKU
3. Bulk-updates `online_availability` and `store_availability` on the `products` table
4. Compares previous vs new availability for watched products → emits `StockEvent` on transitions
5. Purges stock events older than 7 days

Runtime: ~1 min. Scope: all categories (wine, spirits, beer, cider).

### Scheduling

Daily at 2am via systemd timer. On Mondays, the infra backup timer also runs at 2am — see [infra SERVICE_CATALOG.md](https://github.com/vpatrin/infra/blob/main/docs/SERVICE_CATALOG.md) for the full timer schedule.

Source files: [`deploy/systemd/coupette-availability.service`](../deploy/systemd/coupette-availability.service) and [`deploy/systemd/coupette-availability.timer`](../deploy/systemd/coupette-availability.timer).

```bash
# Install
sudo cp deploy/systemd/coupette-availability.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coupette-availability.timer

# Status and logs
systemctl status coupette-availability.timer
journalctl -u coupette-availability.service -n 50 --no-pager

# Manual trigger
sudo systemctl start coupette-availability.service
```

### Resilience

Idempotent — if it crashes mid-run, the next run re-diffs from the last saved snapshot. Worst case: a missed transition gets detected 24 hours late. Same no-auto-retry policy as the scraper.

---

## Migrations

### Rules

- **Model = source of truth** — columns, indexes, constraints all defined on `core/db/models.py`
- **Forward-only in production** — never run `downgrade()` in prod; write a new migration to fix mistakes
- **`downgrade()` is a dev convenience** — `make reset-db` uses it to replay from scratch
- **Autogenerate limitations** — detects new/removed columns, indexes, type changes; does NOT detect column renames (sees drop+add) or data migrations — hand-add those

### Backward-compatible deploys

If old code and new code run simultaneously during a rolling deploy:

1. Add columns as **nullable** (old code ignores them)
2. Backfill data in a follow-up migration
3. Add NOT NULL constraints only after backfill is complete

Never rename or drop a column that old code still reads.

### Quick reference

| Task | Command |
| --- | --- |
| Apply all pending | `make migrate` |
| Generate migration | `make revision msg="description"` |
| Full reset (dev only) | `make reset-db` |
| Check current version | `cd core && poetry run alembic current` |
| Show history | `cd core && poetry run alembic history` |

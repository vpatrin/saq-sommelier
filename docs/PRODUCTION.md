# Production

Infrastructure-level state, deployment process, and outstanding work for the production VPS.
Step-by-step setup instructions live in the infra repo (private).

---

## Current state

- **VPS**: Hetzner CX22, Debian 13 — `web-01`
- **User**: `victor` (root SSH blocked)
- **Auth**: SSH key only (password auth disabled)
- **Firewall**: Hetzner network firewall + ufw — ports 22/80/443 only
- **DNS**: `victorpatrin.dev` + wildcard `*` → VPS IP (Porkbun)
- **Docker**: Docker CE + Compose plugin installed
- **Swap**: 2G at `/swapfile`, swappiness=10
- **Reverse proxy**: Caddy (SSL + routing via victorpatrin.dev subdomains)
- **Services**: backend, bot, scraper (systemd timer), shared-postgres
- **Deployed**: v1.1.0

---

## Deploying

Tag on main first (see [CHANGELOG.md](../CHANGELOG.md)), then deploy the tag on the VPS.

```bash
git fetch --tags && git checkout vX.Y.Z
diff .env.example .env            # check for new/changed vars
make build                        # rebuild service images (including scraper for next scheduled run)
make migrate                      # apply pending migrations (idempotent, always safe to run)
docker compose up -d backend bot  # restart services
```

If `deploy/` unit files changed (or first deploy):

```bash
sudo cp deploy/saq-scraper.{service,timer} deploy/saq-availability.{service,timer} /etc/systemd/system/
sudo systemctl  daemon-reload
sudo systemctl enable --now saq-scraper.timer saq-availability.timer
```

Verify:

```bash
curl -s localhost:8001/health     # backend responds
# message the bot on Telegram    # bot responds
systemctl status saq-scraper.timer   # timer active, next run scheduled
systemctl status saq-availability.timer   # timer active, next run scheduled
```

Rollback: `git checkout vX.Y.Z && make build && docker compose up -d backend bot`

Migrations are forward-only — never run `downgrade()` in production. Write a new migration to fix mistakes. See [OPERATIONS.md](OPERATIONS.md#forward-only-in-production).

---

## Security

**Done:** SSH hardening (PermitRootLogin no, PasswordAuthentication no), double firewall (Hetzner + ufw, ports 22/80/443 only).

**Infra repo:**
- Fail2ban: SSH brute-force protection
- Unattended-upgrades: automatic security patches

---

## Backups

**Not started.** Biggest production risk — no PostgreSQL backups currently.

**Infra repo:**
- `scripts/backup-db.sh`: daily `pg_dump` + 7-day local retention, systemd timer at 3am

---

## Observability

**Infra repo:**
- Grafana: scraper health + API health dashboards — requires VPS upgrade to CX32 for RAM headroom

---

## Staging

Not needed yet. Revisit when multi-developer or when preview deploys are required.

# Production

Infrastructure-level state and outstanding work for the production VPS.
Application deployment process documented in [DEPLOYMENT.md](DEPLOYMENT.md) (#227, not yet written).
Step-by-step setup instructions live in the [infra repo](https://github.com/vpatrin/infra).

---

## Current state

- **VPS**: Hetzner CX22, Debian 13 — `web-01` (46.225.60.16)
- **User**: `victor` (root SSH blocked)
- **Auth**: SSH key only (password auth disabled)
- **Firewall**: Hetzner network firewall + ufw — ports 22/80/443 only
- **DNS**: `victorpatrin.dev` + wildcard `*` → 46.225.60.16 (Porkbun)
- **Docker**: Docker CE + Compose plugin installed
- **Swap**: 2G at `/swapfile`, swappiness=10
- **Reverse proxy**: Caddy (SSL + routing via victorpatrin.dev subdomains)
- **Services**: backend, bot, scraper (systemd timer), shared-postgres
- **Deployed**: v1.1.0

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

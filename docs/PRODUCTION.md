# Production

Deployment process and app-level production concerns for Coupette.
VPS-level infrastructure (firewall, SSH, TLS, networking) is documented in the [infra repo](https://github.com/vpatrin/infra/blob/main/docs/INFRASTRUCTURE.md).

- **Deployed**: v1.4.0
- **Services**: backend, frontend, bot, scraper (systemd timer), shared-postgres

---

## Deploying

Tag on main first (see [CHANGELOG.md](../CHANGELOG.md)), then deploy the tag on the VPS.

```bash
./deploy/deploy_backend.sh vX.Y.Z        # pull → backup → migrate → bootstrap admin → restart → health check
```

Systemd unit files are synced automatically by `deploy_backend.sh` on every run (diff-before-copy, idempotent).

Verify:

```bash
curl -s localhost:8001/health     # backend responds
# message the bot on Telegram    # bot responds
systemctl status coupette-scraper.timer   # timer active, next run scheduled
systemctl status coupette-availability.timer   # timer active, next run scheduled
```

Rollback: `./deploy/deploy_backend.sh vPREVIOUS` (pulls the previous tag's images from GHCR)

Migrations are forward-only — never run `downgrade()` in production. Write a new migration to fix mistakes. See [OPERATIONS.md](OPERATIONS.md#forward-only-in-production).

---

## Security, backups, and observability

See [infra INFRASTRUCTURE.md](https://github.com/vpatrin/infra/blob/main/docs/INFRASTRUCTURE.md) — these are managed at the VPS level, not per-project.

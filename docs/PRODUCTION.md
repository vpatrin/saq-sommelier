# Production

Deployment process and app-level production concerns for Coupette.
VPS-level infrastructure (firewall, SSH, TLS, networking) is documented in the [infra repo](https://github.com/vpatrin/infra/blob/main/docs/INFRASTRUCTURE.md).

- **Deployed**: v1.4.0
- **Services**: backend, frontend, bot, scraper (systemd timer), shared-postgres

---

## Deploying

Tag on main, push the tag — CD deploys automatically (see [cd.yml](../.github/workflows/cd.yml)).

**Flow:** tag push → build + scan + push to GHCR → GitHub Release → SSH to VPS → `git checkout <tag>` → `deploy_frontend.sh` → `deploy_backend.sh`

**Prerequisites:** `SOPS_AGE_KEY`, `SSH_DEPLOY_*` secrets on GitHub. `sops` installed on VPS.

**What the scripts do:**

- `deploy_frontend.sh` — `yarn build` with tag as `VITE_APP_VERSION`, copies to `/srv/coupette`
- `deploy_backend.sh` — decrypt secrets → pull GHCR images → sync systemd units → backup DB → migrate → restart → health check

Verify:

```bash
curl -s localhost:8001/health     # backend responds
# message the bot on Telegram    # bot responds
systemctl status coupette-scraper.timer   # timer active, next run scheduled
systemctl status coupette-availability.timer   # timer active, next run scheduled
```

Rollback: `git checkout vPREVIOUS && SOPS_AGE_KEY=... ./deploy/deploy_backend.sh` (pulls previous tag's images from GHCR)

Migrations are forward-only — never run `downgrade()` in production. Write a new migration to fix mistakes. See [OPERATIONS.md](OPERATIONS.md#forward-only-in-production).

---

## Security, backups, and observability

See [infra INFRASTRUCTURE.md](https://github.com/vpatrin/infra/blob/main/docs/INFRASTRUCTURE.md) — these are managed at the VPS level, not per-project.

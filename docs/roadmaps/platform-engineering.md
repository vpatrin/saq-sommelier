# Platform Engineering Roadmap

Part of the [project roadmap](../ROADMAP.md). DX tooling, Docker hardening, CI/CD, IaC, backups, security.

## Phase 1 — Developer Experience (~1 day)

- [x] Makefile — dev, test, lint, migrate, scrape, embed, eval, logs, load-test, clean
- [ ] Docker dev environment — docker-compose.dev.yml with hot reload, exposed ports
- [x] .env.example — documents every required variable

## Phase 2 — Production Docker (~1 day)

- [ ] docker-compose.prod.yml — no debug ports, resource limits, health checks, restart policies, log rotation
- [x] Dockerfile hardening — multi-stage builds, non-root user, minimal images (#3, #4)
- [x] Compose profiles — dev postgres, on-demand scraper (#3, #4)
- [ ] Docker secrets — sensitive values via files, not env vars

## Phase 3 — CI/CD Pipeline (~1 day)

- [x] CI pipeline — lint + test on every PR, caching, Hadolint (#2, #72, #73)
- [ ] CI enhancement — Docker build + eval check on every PR
- [ ] CD pipeline — push to main → build → push to GHCR → deploy to VPS
- [ ] Rollback strategy — timestamped image tags, rollback script, docs/RUNBOOK.md

## Phase 4 — Infrastructure as Code (~2 days)

- [ ] VPS bootstrap script — `infra/scripts/setup-vps.sh` (Docker, swap, Caddy, networks, deploy user)
- [ ] Ansible playbooks — setup.yml, deploy.yml, backup.yml, rollback.yml with roles (common, docker, caddy, app, monitoring)
- [ ] Terraform (Hetzner) — VPS, SSH key, firewall, DNS

## Phase 5 — Backup & Disaster Recovery (~half day)

- [ ] `infra/scripts/backup-db.sh` — PostgreSQL dump + ChromaDB volume backup, 7-day retention
- [ ] Systemd timer — daily 3am backup
- [ ] docs/DISASTER_RECOVERY.md — recovery procedures for container crash, VPS death, bad deploy, DB corruption, ChromaDB corruption

## Phase 6 — Security Hardening

Moved to dedicated [Security Roadmap](security.md). Dependabot (#61) and Hadolint (#73) already done.

## Phase 7 — Advanced Platform (~2 days, portfolio polish)

- [ ] Grafana dashboards as code — provisioned from JSON files in repo
- [x] Port assignment convention (#53)
- [ ] `/health/detailed` endpoint — see [SRE Phase 2](sre.md) for health check design
- [ ] Terraform GCP — Cloud Run + Cloud SQL + Artifact Registry (documented only, not deployed)

# Security Roadmap

Part of the [project roadmap](../ROADMAP.md). Access control, supply chain, secret management, infrastructure hardening.

## Phase 1 — Bot Access Control (~half day)

- [x] Telegram user allowlisting — `ALLOWED_USER_IDS` env var, reject unknown users with polite message (#178)
- [x] Per-user rate limiting — throttle commands to prevent abuse (#178)
- [ ] Command audit logging — log user_id + command to stdout for traceability
- [ ] Dynamic allowlist — `/allow` admin command + PostgreSQL table, no restart to add users - To investigate

## Phase 2 — API Security (~half day)

- [x] CORS origins — env-driven allowlist via BackendSettings (PR #80)
- [x] Input validation — query param bounds, max lengths (PR #80)
- [ ] API authentication — bot→backend calls require API key (`X-API-Key` header)
- [ ] Rate limiting middleware — slowapi or custom, per-IP, protect against crawlers on CX22

## Phase 3 — Supply Chain Security (~half day)

- [x] Dependabot — weekly updates for pip + github-actions (#61)
- [x] Hadolint — Dockerfile linting in CI (#73)
- [x] pip-audit in CI — fail on known vulnerabilities in dependencies (#194)
- ~~Trivy container scan~~ — descoped (#74)

## Phase 4 — Secret Management (~half day)

- [ ] Docker secrets for production — bot token, DB password, future Claude API key via files, not env vars
- [ ] Secret rotation procedure — documented steps for rotating bot token, DB credentials
- [x] gitleaks in CI — scan git history for committed secrets (#194)
- [ ] `.env` audit — verify no secrets committed in repo history (`git log -S`)

## Phase 5 — Infrastructure Hardening (~1 day)

- [ ] SSH hardening — disable root login, disable password auth, key-only
- [ ] UFW firewall — allow only 22 (SSH), 80/443 (Caddy), deny all else
- [ ] Fail2ban — protect SSH against brute force
- [ ] Unattended-upgrades — automatic OS security patches
- [ ] Docker daemon hardening — no `--privileged`, read-only rootfs where feasible

## Phase 6 — Security Monitoring (~half day)

- [ ] Security headers audit — verify Caddy sets HSTS, X-Content-Type-Options, X-Frame-Options
- [ ] Failed request logging — 4xx/5xx patterns for anomaly detection
- [ ] Quarterly dependency audit — manual review of pip-audit + Trivy reports

## Phase 7 — Documentation (~half day, portfolio)

- [ ] SECURITY.md — responsible disclosure policy (even for a personal project, signals maturity)
- [ ] Threat model — identify assets, trust boundaries, attack surfaces (bot, API, scraper, VPS)
- [ ] Security checklist for new services — template for adding a service securely

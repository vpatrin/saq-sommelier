# Security

Application-level security model. VPS-level hardening (firewall, SSH, TLS) lives in the [infra repo](https://github.com/vpatrin/infra/blob/main/docs/INFRASTRUCTURE.md).

---

## Authentication

### Telegram OAuth (identity)

Users authenticate via the [Telegram Login Widget](https://core.telegram.org/widgets/login). The backend verifies the HMAC-SHA-256 signature per Telegram's spec:

1. Build a check string from sorted `key=value` pairs (excluding `hash`), joined by `\n`
2. Derive the secret key: `SHA256(bot_token)`
3. Compute `HMAC-SHA256(secret_key, check_string)`
4. Compare with `hmac.compare_digest` (timing-safe)

Payloads older than 24 hours are rejected to prevent replay attacks.

**Code:** `backend/services/auth.py` → `_verify_telegram_hash()`

### JWT (sessions)

- **Library:** PyJWT (python-jose is unmaintained with CVEs)
- **Algorithm:** HS256
- **Expiry:** 7 days — re-login is one Telegram Widget tap, no refresh tokens needed
- **Claims:** `sub` (user ID), `telegram_id`, `role`, `exp`, `iat`
- **Signing key:** `JWT_SECRET_KEY` env var, required in production (startup guard)

**Why no refresh tokens:** The threat model doesn't warrant it. This is a wine discovery app for a closed beta, not a financial product. The cost of implementing refresh token rotation exceeds the security benefit when re-login is a single tap.

**Code:** `backend/services/auth.py` → `_create_jwt()`, `backend/auth.py` → `get_current_active_user()`

### Dual auth (web + bot)

Two authentication paths through a single `verify_auth()` dependency:

| Client         | Method           | Header                          |
|----------------|------------------|---------------------------------|
| Web app        | JWT bearer token | `Authorization: Bearer <token>` |
| Bot → backend  | Shared secret    | `X-Bot-Secret: <secret>`        |

Bot secret takes priority — if the header is present and valid, JWT validation is skipped and `verify_auth` returns `None` (no user context). Required in production, no-op when empty (dev convenience).

**Code:** `backend/auth.py` → `verify_auth()`

---

## Flows

### New user registration (backend)

1. Admin generates invite code: `POST /api/admin/invites` (JWT + admin role required)
2. Admin shares code out-of-band (DM, email)
3. User opens web app → Telegram Login Widget signs payload
4. User sends `POST /api/auth/telegram` with `{ id, first_name, username, photo_url, auth_date, hash, invite_code }`
5. Backend verifies: auth freshness (24h) → HMAC signature → user not found → invite code valid and unused
6. Atomic transaction: INSERT user (`role=user`, `is_active=true`) + redeem invite (`used_by_id`, `used_at`)
7. Returns JWT (`{ access_token, token_type: "bearer" }`)

### Existing user login (backend)

1. Telegram Login Widget signs payload
2. `POST /api/auth/telegram` with `{ id, first_name, ..., hash }` (invite_code ignored if present)
3. Backend verifies: auth freshness → HMAC → user found → `is_active` check
4. UPDATE `last_login_at`, `username`, `first_name`
5. Returns JWT

### Authenticated API request (backend)

```text
Request with Authorization: Bearer <jwt>
  → verify_auth()
    → no X-Bot-Secret → get_current_active_user()
      → decode JWT → find user by ID → check is_active
      → return User
  → handler runs
```

### Bot → backend service call

```text
Request with X-Bot-Secret: <secret>
  → verify_auth()
    → secret matches → return None (no user context, bot is trusted)
  → handler runs
```

### Bot user authorization

```text
Telegram user sends message
  → access_gate() [group -2]
    → cache hit (<1h, authorized=true) → pass
    → cache miss → GET /api/auth/telegram/check (X-Bot-Secret)
      → 204 → cache authorized=true
      → 404/403 → reject message, ApplicationHandlerStop
      → 5xx/timeout → fail open (allow through)
  → rate_limit_gate() [group -1]
  → handler
```

### Admin bootstrap

Idempotent `make create-admin` command — creates or promotes the admin user from `ADMIN_TELEGRAM_ID` env var.

```bash
# Bare metal (reads .env via Makefile)
make create-admin
```

Safe to run on every deploy — no-ops if admin already exists with correct role.

---

## Authorization

### Route guards

All API routes require authentication except:

- `GET /health` — health check
- `POST /api/auth/telegram` — login endpoint
- `GET /api/auth/telegram/check` — user existence check (`require_bot_secret` guard)

JWT-authenticated requests decode the token, look up the user, and reject if `is_active` is false — deactivation is enforced on every request, not just at login.

Admin routes (`/api/admin/*`) require `role == "admin"` via `verify_admin()` dependency.

**Code:** `backend/auth.py` → `verify_auth()`, `get_current_active_user()`, `backend/app.py` (router `dependencies=` wiring)

### Invite code gate (closed beta)

New users must present a single-use invite code at first login. Existing users skip this check.

- Codes: `secrets.token_urlsafe(16)` (~128 bits entropy, 22 chars)
- Admin generates via `POST /api/admin/invites`
- Redeemed atomically: `used_by_id` and `used_at` set on the `invite_codes` row
- Invalid or already-used codes → 401

**Code:** `backend/services/auth.py` → `authenticate_telegram()`, `backend/repositories/invites.py`

### Bot access gate

The Telegram bot checks user registration before handling any message:

1. `access_gate()` middleware runs at handler group -2 (before all handlers)
2. Calls `GET /api/auth/telegram/check?telegram_id=...` on the backend: check user exists and is active, by telegram id
3. Caches the result in `context.user_data` for 1 hour (avoids hammering backend)
4. Unauthorized users get a rejection message + `ApplicationHandlerStop`

**Fail-open on backend unavailability:** If the backend is unreachable (timeout, 5xx), the bot allows the user through. Rationale: the bot is the primary interface during closed beta — denying access when the auth service is down helps nobody. Recently-verified users remain cached.

**Code:** `bot/bot/middleware.py` → `access_gate()`

### User lifecycle

- `is_active` boolean on the `users` table replaces the old `ALLOWED_USER_IDS` env var
- Deactivation is instant: checked at JWT decode, at bot middleware, and at the `/check` endpoint
- No self-service admin promotion — first admin is set manually via `UPDATE users SET role='admin'`

---

## Rate Limiting

Per-user sliding window rate limiter on the bot side. Silently drops updates from users exceeding the threshold.

**Code:** `bot/bot/middleware.py` → `RateLimiter`, `rate_limit_gate()`

No rate limiting on the login endpoint yet (tech debt — Telegram's HMAC makes brute-force pointless, but defense-in-depth would be better).

---

## CI/CD Security

| Tool       | What it catches                               | Where          |
|------------|-----------------------------------------------|----------------|
| Dependabot | Outdated dependencies (pip + GitHub Actions)  | Weekly PRs     |
| pip-audit  | Known vulnerabilities in Python packages      | CI per service |
| gitleaks   | Secrets committed in code                     | CI             |
| Hadolint   | Dockerfile anti-patterns                      | CI             |
| Trivy      | Container image vulnerabilities               | CI on PR       |

---

## Application Hardening

- **CORS:** Env-driven `CORS_ORIGINS`, locked to `localhost:5173` in dev
- **Input validation:** Pydantic models with `max_length` constraints on all string fields
- **Production startup guards:** Backend refuses to start without `BOT_SECRET`, `JWT_SECRET_KEY`, and `TELEGRAM_BOT_TOKEN`
- **DB password encoding:** URL-encoded in connection string to handle special characters
- **Non-root Docker containers:** All Dockerfiles create and switch to a non-root user
- **No debug ports in production:** `docker-compose.prod.yml` exposes only what Caddy needs

---

## Threat Model

| Threat                  | Mitigation                                                     | Residual risk                                                   |
|-------------------------|----------------------------------------------------------------|-----------------------------------------------------------------|
| HMAC forgery            | `hmac.compare_digest` (timing-safe), SHA256 key derivation     | None — standard Telegram spec                                   |
| Auth replay             | 24h `auth_date` freshness check                                | Replay within 24h window (acceptable)                           |
| JWT theft               | 7-day expiry, `is_active` check on every request               | No revocation before expiry                                     |
| Invite brute-force      | 128-bit entropy codes, single-use                              | Negligible                                                      |
| Bot impersonation       | `X-Bot-Secret` required in production                          | Compromised secret = full bot access                            |
| Deactivated user access | `is_active` checked at JWT decode + bot middleware             | Cached auth in bot (up to 1h stale)                              |
| Backend down            | Bot fails open with cached auth                                | Unauthenticated access during outage (bounded by cache TTL)     |
| XSS -> token theft      | React JSX auto-escaping, no `dangerouslySetInnerHTML`          | localStorage accessible to XSS (mitigate with CSP -- planned)  |
| LLM API key leak        | Env vars only, never in frontend or logs, sops-encrypted prod  | Billing exposure if VPS compromised                             |

---

## Known Limitations

- **No JWT revocation** — can't invalidate a token before its 7-day expiry. Mitigated by `is_active` flag checked on every API call.
- **No rate limit on login** — `POST /api/auth/telegram` is public. Low risk due to HMAC requirement.
- **Single admin** — only one admin supported via `ADMIN_TELEGRAM_ID`. Multi-admin would need a promotion endpoint.
- **Docker secrets not adopted** — credentials live in `.env` on disk. Planned migration to Docker secrets.
- **Bot auth cache** — up to 1 hour stale. A deactivated user can keep using the bot for up to 1 hour after deactivation.

---

## Security Log

### 2026-02-15 — API hardening baseline (#72, #80)

**Context:** First public-facing API endpoints going live — needed baseline security before any users touch it.
**Action:** CORS lockdown (env-driven origins), Pydantic input validation with `max_length` on all string fields, Hadolint in CI for Dockerfile hygiene.

### 2026-02-21 — CI security scanning (#194, #217)

**Context:** Dependencies growing — manual dep auditing doesn't scale, needed automated gates before merge.
**Action:** pip-audit + gitleaks in CI. Later hardened with timeouts and concurrency controls.

### 2026-03-08 — Supply chain + secrets hardening (#313)

**Context:** Preparing for auth system — unpinned installers are supply chain risk, special chars in DB password broke connections silently, production had no startup guards for required secrets.
**Action:** Pinned Poetry installer hash, URL-encoded DB password in connection string, `BOT_SECRET` startup guard in production.

### 2026-03-09 — Auth system (#353–#358)

**Context:** Needed closed beta access control before shipping the web app. Re-login is one tap (Telegram Widget), so refresh token rotation complexity unjustified for wine app closed beta.
**Decision:** Telegram OAuth + JWT + invite codes. HS256 over RS256 (single service, no token sharing). 7-day expiry, no refresh tokens.

### 2026-03-09 — Container image scanning (#360)

**Context:** Auth system shipping — containers now handle user credentials. pip-audit catches Python deps but misses OS-level CVEs.
**Action:** Trivy scan on built Docker images in CI (PR checks + tag push).

### 2026-03-19 — Deploy secrets encryption (#482)

**Context:** Automated CD pipeline needed secrets on the runner without storing them in plaintext — GitHub Actions secrets are fine for CI, but the deploy script needs the full `.env`.
**Action:** sops + age encryption for production secrets. Decrypted at deploy time only. Simpler than Vault for a single-VPS setup.

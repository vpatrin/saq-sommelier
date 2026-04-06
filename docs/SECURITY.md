# Security

Application-level security model. VPS-level hardening (firewall, SSH, TLS) lives in the [infra repo](https://github.com/vpatrin/infra/blob/main/docs/INFRASTRUCTURE.md).

---

## Authentication

### OAuth providers (identity)

Users authenticate via third-party OAuth providers. The backend handles the full OAuth 2.0 flow: CSRF state generation, authorization redirect, code exchange, and user info fetch.

| Provider  | Scopes              | User info endpoint                       |
|-----------|---------------------|------------------------------------------|
| GitHub    | `user:email`        | `/user` + `/user/emails` (parallel)      |
| Google    | `openid email profile` | `/oauth2/v3/userinfo` (single call)   |
| Telegram  | Widget HMAC         | Payload included in widget callback      |

**CSRF protection:** Random state token stored in Redis (`oauth:state:<token>`, 10 min TTL), consumed atomically on callback via `DELETE`. Prevents cross-site request forgery on OAuth callbacks.

**Exchange code pattern:** After successful OAuth, the backend stores the JWT in Redis under a random single-use code (`oauth:exchange:<code>`, 60s TTL). The browser is redirected to the frontend with `?code=...`, which swaps it for the JWT via `GET /api/auth/exchange`. This avoids putting JWTs in URLs (logs, referrer, browser history).

**Waitlist gate:** New users (no existing account or email match) must have an approved waitlist entry. Unapproved users are redirected to the frontend with `?error=not_approved`.

**Account linking:** If a user logs in with a new OAuth provider but their email matches an existing account, the new provider is linked automatically — one user, multiple login methods.

**Code:** `backend/api/auth.py` (endpoints), `backend/services/auth.py` → `create_oauth_session()`, `backend/services/github_oauth.py`, `backend/services/google_oauth.py`

### Telegram HMAC (notification linking)

The Telegram Login Widget uses HMAC-SHA-256 verification per Telegram's spec. Used in Settings to link a Telegram account for notifications and bot access (not as a login provider). Payloads older than 24 hours are rejected to prevent replay attacks.

**Code:** `backend/services/auth.py` → `verify_telegram_data()`, `_verify_telegram_hash()`

### JWT (sessions)

- **Library:** PyJWT (python-jose is unmaintained with CVEs)
- **Algorithm:** HS256
- **Expiry:** 7 days
- **Claims:** `sub` (user ID), `role`, `display_name`, `exp`, `iat`
- **Signing key:** `JWT_SECRET_KEY` env var, required in production (startup guard)

**Why no refresh tokens:** This is a wine discovery app for a closed beta, not a financial product. Re-login is one OAuth click. The cost of implementing refresh token rotation exceeds the security benefit.

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

### OAuth login (GitHub / Google)

1. User clicks "Sign in with GitHub/Google" on the login page
2. `GET /api/auth/{provider}/login` — generates CSRF state token (Redis, 10 min TTL), redirects to provider's authorize URL
3. User authenticates on the provider's site
4. Provider redirects to `GET /api/auth/{provider}/callback?code=...&state=...`
5. Backend validates state (atomic Redis DELETE), exchanges code for access token, fetches user info
6. `create_oauth_session()` — upserts user (existing account → link provider, new user → check waitlist gate), mints JWT
7. JWT stored in Redis under a random exchange code (60s TTL)
8. Redirects to `FRONTEND_URL/auth/callback?code=...` (or `?error=not_approved` / `?error=invalid_state`)
9. Frontend calls `GET /api/auth/exchange?code=...` → receives JWT, stores in localStorage

### Telegram account linking

1. Authenticated user clicks "Connect" in Settings → Telegram Login Widget
2. `POST /users/me/telegram` — verify HMAC, check for conflicts, set `telegram_id` on user
3. Unlinking: `DELETE /users/me/telegram` — clears `telegram_id`

### Authenticated API request

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

Idempotent `make create-admin` command — creates or promotes the admin user from `ADMIN_EMAIL` env var. Safe to run on every deploy.

---

## Authorization

### Route guards

All API routes require authentication except:

- `GET /health` — health check
- `GET /api/auth/telegram/check` — user existence check (`require_bot_secret` guard)
- `GET /api/auth/github/login` — OAuth redirect (generates state, no user data)
- `GET /api/auth/github/callback` — OAuth callback (validates state + code)
- `GET /api/auth/google/login` — OAuth redirect
- `GET /api/auth/google/callback` — OAuth callback
- `GET /api/auth/exchange` — exchange code for JWT (single-use, 60s TTL)
- `POST /api/waitlist` — public waitlist submission

JWT-authenticated requests decode the token, look up the user, and reject if `is_active` is false — deactivation is enforced on every request, not just at login.

Admin routes (`/api/admin/*`) require `role == "admin"` via `verify_admin()` dependency.

**Code:** `backend/auth.py` → `verify_auth()`, `get_current_active_user()`, `backend/app.py` (router `dependencies=` wiring)

### Waitlist gate (closed beta)

New OAuth users must have an approved waitlist entry (matched by email). Visitors submit their email via the landing page form, admins approve via the admin panel. Approved users receive a confirmation email via Resend.

**Code:** `backend/services/auth.py` → `create_oauth_session()`, `backend/repositories/waitlist.py`

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
- Admin bootstrap via `ADMIN_EMAIL` env var + `make create-admin` (idempotent, verified at startup)

---

## Rate Limiting

**Backend (SlowAPI):** Tiered per-user rate limits via `slowapi`. Keyed by user ID (JWT) or IP (unauthenticated). Limits: 100/min global, 10/min auth, 3/min waitlist, 20/min LLM. ADR: [0009-rate-limiting-tiered-strategy](decisions/0009-rate-limiting-tiered-strategy.md).

**Bot:** Per-user sliding window rate limiter. Silently drops updates from users exceeding the threshold.

**Code:** `backend/rate_limit.py`, `bot/bot/middleware.py` → `RateLimiter`, `rate_limit_gate()`

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
- **Production startup guards:** Backend refuses to start without `BOT_SECRET`, `JWT_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FRONTEND_URL`, `BACKEND_URL`
- **DB password encoding:** URL-encoded in connection string to handle special characters
- **Non-root Docker containers:** All Dockerfiles create and switch to a non-root user
- **No debug ports in production:** `docker-compose.prod.yml` exposes only what Caddy needs

---

## Threat Model

| Threat                  | Mitigation                                                     | Residual risk                                                   |
|-------------------------|----------------------------------------------------------------|-----------------------------------------------------------------|
| OAuth CSRF              | Random state token in Redis, atomic consume on callback        | None — standard OAuth 2.0 spec                                  |
| OAuth code interception | Exchange codes are single-use (GETDEL), 60s TTL                | 60s window if code is intercepted (HTTPS mitigates)             |
| HMAC forgery (Telegram) | `hmac.compare_digest` (timing-safe), SHA256 key derivation     | None — standard Telegram spec                                   |
| Auth replay (Telegram)  | 24h `auth_date` freshness check                                | Replay within 24h window (acceptable)                           |
| JWT theft               | 7-day expiry, `is_active` check on every request               | No revocation before expiry                                     |
| Bot impersonation       | `X-Bot-Secret` required in production                          | Compromised secret = full bot access                            |
| Deactivated user access | `is_active` checked at JWT decode + bot middleware              | Cached auth in bot (up to 1h stale)                             |
| Backend down            | Bot fails open with cached auth                                | Unauthenticated access during outage (bounded by cache TTL)     |
| XSS -> token theft      | React JSX auto-escaping, no `dangerouslySetInnerHTML`          | localStorage accessible to XSS (mitigate with CSP — planned)   |
| LLM API key leak        | Env vars only, never in frontend or logs, sops-encrypted prod  | Billing exposure if VPS compromised                             |
| OAuth endpoint abuse    | Waitlist gate, state validation, SlowAPI rate limits            | Rate-limited but public endpoints                               |

---

## Known Limitations

- **No JWT revocation** — can't invalidate a token before its 7-day expiry. Mitigated by `is_active` flag checked on every API call.
- **Single admin** — only one admin supported via `ADMIN_EMAIL`. Multi-admin would need a promotion endpoint.
- **Docker secrets not adopted** — credentials live in `.env` on disk. Planned migration to Docker secrets.
- **Bot auth cache** — up to 1 hour stale. A deactivated user can keep using the bot for up to 1 hour after deactivation.
- **JWT in localStorage** — accessible to XSS. HttpOnly cookie migration planned in ENGINEERING.md backlog.

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

### 2026-04-05 — GitHub + Google OAuth (#595, #591)

**Context:** Replacing invite codes with OAuth for user registration. Waitlist gate controls access instead.
**Decision:** OAuth 2.0 with CSRF state tokens (Redis), single-use exchange codes. GitHub + Google as providers. OIDC `id_token` decoding deferred — `/userinfo` approach is simpler and consistent across providers.

### 2026-04-05 — Email-based admin + Telegram as notification channel

**Context:** Admin bootstrap relied on `ADMIN_TELEGRAM_ID`, coupling admin identity to Telegram. Telegram login on the web app was redundant with Google/GitHub OAuth.
**Action:** Admin identified by `ADMIN_EMAIL`. Telegram removed from login page, moved to Settings as a linked notification channel (`POST /users/me/telegram`). Telegram Login Widget HMAC verification reused for linking.

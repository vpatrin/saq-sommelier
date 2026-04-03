# ADR 0008: OAuth2 Authorization Flow Security Design

**Date:** 2026-04-02
**Status:** Accepted

## Context

Adding GitHub + Google OAuth2 login to the FastAPI backend. The frontend is a React SPA with JWTs stored in localStorage. The app is small and invite-gated, running on a Hetzner VPS with no Redis previously. Goals: CSRF protection, code interception protection, replay protection, and compliance with RFC 6749 + RFC 9700 (OAuth2 Security BCP).

## Options considered

1. **State parameter only (signed JWT, stateless)** — simple, no DB/cache, but no replay protection; violates RFC 9700 "state MUST be invalidated after use".
2. **Opaque token + PostgreSQL `oauth_states` table** — compliant, no new infra, but requires a periodic cleanup job for expired rows.
3. **Opaque token + Redis** — compliant, native TTL eliminates cleanup job, sets Redis up for future use cases (rate limiting, caching).
4. **PKCE alone (no state)** — protects code exchange but not CSRF at flow initiation.
5. **PKCE + encrypted state + Redis nonce** — defense-in-depth, fully RFC 9700 compliant. Chosen.

## Decision

PKCE (S256) + AES-256-GCM encrypted + HMAC-SHA256 signed state + Redis-backed single-use nonce.

- `code_verifier`: 32 random bytes, stored in Redis (10 min TTL), sent with token exchange
- `code_challenge`: SHA-256(code_verifier), sent to provider
- `state`: `{nonce, mode, user_id?, exp}` encrypted with AES-256-GCM, signed with HMAC-SHA256
- `nonce`: stored in Redis (10 min TTL), deleted on first use (single-use)
- `exchange_code`: opaque random token (60s TTL, single-use, stored in Redis as `exchange:{code} → jwt`); backend callback redirects to `{FRONTEND_URL}/auth/callback?code={exchange_code}`; frontend immediately calls `POST /api/auth/exchange` to get the JWT in the response body — JWT never appears in a URL, server log, or Referer header

**What each layer protects against:**

| Layer | Threat |
|---|---|
| PKCE | Code interception — stolen auth code is useless without the verifier |
| State encryption (AES-256-GCM) | Payload confidentiality — logs and referrer headers can't leak `user_id` or `mode` |
| State HMAC | Forgery — attacker can't craft a valid state without the signing key |
| Redis nonce (single-use) | Replay — a valid state can't be reused after the callback |
| State expiry | Stale flow protection |
| Exchange code (60s, single-use) | JWT delivery — token never appears in URL, logs, or Referer headers |

## Intentional tradeoffs

1. **No Telegram login** — Telegram widget stays for bot alerts only (linked from Settings). GitHub/Google guarantee a verified email; Telegram does not. Email is the identity anchor for account linking and deduplication.
2. **No email/password** — OAuth-only. Eliminates password storage, reset flows, and credential stuffing risk. Users have GitHub/Google accounts. Security wins over convenience for this app.
3. **JWT in localStorage** — known XSS risk. HttpOnly cookie migration is a separate refactor. Threat model (small invite-gated app) makes this acceptable short-term. Documented as a known gap.
4. **Redis over PostgreSQL for state** — adds new infra. Native TTL eliminates the cleanup job; Redis will be needed for rate limiting later; idle memory usage (~5 MB) is negligible on a 4 GB VPS.

## Consequences

- New infra: Redis container (managed in infra repo, requires coordination)
- New config vars: `STATE_ENCRYPTION_KEY`, `REDIS_URL`
- `cryptography` lib added to backend dependencies (AES-256-GCM)
- Fully RFC 9700 compliant on the authorization flow
- localStorage JWT remains a known gap — a future ADR will cover the HttpOnly cookie migration

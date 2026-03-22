# Auth System

Telegram OAuth + JWT tokens + invite code gating. ADR: [0004-telegram-first-auth](../decisions/0004-telegram-first-auth.md).

---

## Flow

```
User → Telegram Login Widget → Telegram OAuth → signed payload → Browser
Browser → POST /api/auth/telegram (payload + invite_code) → Backend
Backend → verify HMAC → upsert user → redeem invite → issue JWT → 200
Frontend → stores JWT in localStorage → Authorization: Bearer <token> on all calls
```

## Telegram HMAC Verification

Telegram signs the OAuth payload with the bot token. Backend recomputes the signature to verify integrity.

1. Build `check_string`: sorted `key=value` pairs joined by `\n`, excluding `hash` and `invite_code`
2. Derive key: `SHA-256(bot_token)` → 32-byte digest
3. Compute: `HMAC-SHA-256(key, check_string)`
4. Compare: `hmac.compare_digest(computed, payload.hash)` (timing-safe)

Payload must be < 24h old (`auth_date` check).

## JWT Token

**Algorithm:** HS256 · **Expiry:** 7 days · **Secret:** `JWT_SECRET_KEY` env var

Claims:

| Claim | Type | Example |
|---|---|---|
| `sub` | str | `"1"` (user ID) |
| `telegram_id` | int | `12345` |
| `role` | str | `"user"` or `"admin"` |
| `first_name` | str | `"Alice"` |
| `exp` | datetime | now + 7 days |
| `iat` | datetime | now |

Frontend decodes the payload (base64, no verification) to extract user info. Checks `exp` on load to clear expired tokens.

## Dual Auth Paths

| Path | Header | Returns | Used by |
|---|---|---|---|
| Web (JWT) | `Authorization: Bearer <token>` | `User` object | React frontend |
| Bot (shared secret) | `X-Bot-Secret: <secret>` | `None` (no user context) | Telegram bot |

Bot secret checked first. If present and valid, JWT is skipped. Bot callers must pass `user_id` explicitly on endpoints that need it.

## Invite Code Lifecycle

1. **Generate**: Admin calls `POST /api/admin/invites` → `secrets.token_urlsafe(16)` → ~22-char code
2. **Distribute**: Admin shares code out-of-band (message, link)
3. **Redeem**: New user includes `invite_code` in login payload → backend validates (`used_by_id IS NULL`) → marks as used
4. **Single-use**: Query filters on `used_by_id IS NULL`. Once redeemed, code is permanently consumed.

Existing users skip the invite check entirely.

## User Model

| Field | Type | Notes |
|---|---|---|
| `telegram_id` | BigInteger | Unique, indexed |
| `username` | String, nullable | Telegram @handle |
| `first_name` | String | Display name |
| `role` | String | `"user"` (default) or `"admin"` |
| `is_active` | Boolean | Deactivation flag |
| `last_login_at` | DateTime | Updated on each auth |

## Role Enforcement

- **Regular routes**: `verify_auth()` → accepts JWT or bot secret
- **Admin routes**: `verify_admin()` → requires JWT with `role=admin`. Bot callers rejected.
- **Deactivation**: Admin PATCHes `/api/admin/users/{id}` with `is_active=false`. Cannot deactivate other admins.

## Error Cases

| Scenario | Status |
|---|---|
| Payload > 24h old | 401 |
| HMAC signature invalid | 401 |
| User deactivated | 403 |
| New user, no invite code | 403 |
| New user, invalid/used invite | 401 |
| JWT missing/expired/malformed | 401 |
| User not found (JWT sub) | 401 |

## Environment Variables

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Signs/verifies JWTs |
| `TELEGRAM_BOT_TOKEN` | Verifies Telegram OAuth signatures |
| `BOT_SECRET` | Shared secret for bot → backend calls |
| `ADMIN_TELEGRAM_ID` | Bootstrap admin user (verified at startup) |

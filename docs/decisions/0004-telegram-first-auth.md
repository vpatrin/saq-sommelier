# ADR 0004: Telegram OAuth as Primary Auth

**Date:** 2026-03-09
**Status:** Accepted

## Context

Coupette needs user authentication for the web app and API. The Telegram bot already has an active user base (~20 users). We need an auth strategy that works for both the web app and the bot without requiring users to create yet another account.

## Options considered

1. **Email/password** — traditional auth, requires email verification, password reset flow, account recovery.
2. **Google/GitHub OAuth** — well-supported, but requires users to have accounts on those platforms and doesn't connect to their Telegram identity.
3. **Telegram Login Widget** — OAuth via Telegram, links web identity to bot identity automatically.
4. **Magic links** — passwordless email auth, simpler than email/password but still requires email infrastructure.

## Decision

Option 3: Telegram Login Widget for web auth, JWT tokens for API sessions, invite codes for access control.

## Rationale

- **Zero friction for existing users.** Bot users already have a Telegram account. One click to log into the web app — no new credentials, no email verification.
- **Unified identity.** The same `telegram_id` identifies a user across bot and web app. Watches created in the bot appear in the web dashboard. No account linking needed.
- **No email infrastructure.** No need for SMTP, email templates, verification flows, or password reset. Telegram handles identity verification.
- **Invite codes gate access.** The app isn't public yet. Invite codes (admin-generated, single-use) control who can register. This avoids building a waitlist or approval flow.

## Auth flow

1. User visits `coupette.club` → sees Telegram Login Widget
2. Widget redirects to Telegram → user authorizes → callback with HMAC-signed payload
3. Backend verifies HMAC using bot token, creates/finds user, issues JWT
4. JWT used for all subsequent API calls (15-day expiry)
5. Bot authenticates via `X-Bot-Secret` header (shared secret, not JWT)

## Consequences

- **Telegram dependency.** If Telegram goes down or changes their OAuth, auth breaks. Acceptable — the entire bot UX already depends on Telegram.
- **No non-Telegram users.** Intentional — Telegram is the acquisition channel.
- **JWT secret rotation** requires all active sessions to re-authenticate. Acceptable at current scale.
- **Adding a second OAuth provider** (Google, GitHub) is architecturally straightforward — the `users` table uses an internal `id` as PK, not `telegram_id`.

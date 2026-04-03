# Roadmap

Product phases below. Engineering discipline targets (testing, security, observability, SRE, platform, ML/MLOps) in [ENGINEERING.md](ENGINEERING.md).

---

## Product

### Phases 0–10 ✅

Scaffolding, scraping, data layer, API, Telegram bot, AI layer (RAG + Claude), auth & security, React frontend shell, chat endpoint + interface, intent router. See git history and closed issues for details.

### Visual Identity Rework *(milestone: Visual Identity Rework)*

Premium warm theme replacing the brutalist/terminal aesthetic. Cross-cutting UX effort before Phase 11.

- [x] Theme foundation — tokens, fonts, sidebar (#534)
- [x] Landing page + login restyle (#536)
- [ ] Age gate (18+) on first visit (#535)
- [x] Chat page + wine card restyle (#537)
- [x] Search, watchlist, stores restyle + empty states (#538)
- [x] Wine detail slide panel (#539)
- [x] User menu dropdown (#540)
- [x] Global wine detail panel — accessible from chat, watchlist, search (#562)

Design mockups in `ui/` — organized by feature. Screenshots in `ui/screenshots/`.

### Tasting Journal *(milestone: Tasting Journal)*

Log wines you've tasted with 100-point ratings and tasting notes. SAQ catalog wines only (select by SKU). "Log tasting" action on product cards in search results and chat. Dedicated "My Tastings" page in sidebar.

- [x] TastingNote model + migration (#442)
- [x] Tasting CRUD endpoints (#443)
- [x] "Log tasting" inline form on product cards (#444)
- [x] My Tastings page (#445)
- [x] Surface "You rated: 92" on product cards in search results (#446)

Design reference: `ui/journal/journal.html`, `ui/journal/notif-noteview.html`

### Taste Profile *(milestone: Taste Profile)*

Build a user taste profile from watches, recommendation feedback, and tasting journal scores. MVP signals — no cellar data needed yet. Inject into recommendation prompts for personalization. Displayed as a sidebar widget, not a standalone page.

- [ ] Taste profile computation — aggregate signals into structured preferences (regions, grapes, price range, style)
- [ ] Adventure temperature — controls how exploratory vs conservative recommendations are
- [ ] Profile context injection — pass taste profile + adventure setting to Claude for personalized recommendations
- [ ] Sidebar taste profile card — only shown after threshold (5+ tastings or 3+ watches)

Design reference: `ui/taste-profile/palais.html`

### Weekly Digest

Automated personalized summary of new/restocked wines matching user's taste profile. Delivered via Telegram DM (per-user, not group chat — #120 scope updated). This reintroduces the bot as a content delivery channel beyond alerts.

- [ ] Weekly job — query new/restocked products since last run
- [ ] Per-user personalization — filter by taste profile preferences
- [ ] Claude curation — summarize top picks with brief reasoning
- [ ] Telegram delivery — summary + link to full digest on web app
- [ ] Digest web page — weekly picks with full wine cards and tasting/cellar actions

### Cellar *(milestone: Cellar)*

Track wines you have at home. SAQ catalog wines only. "Add to cellar" action on product cards. Quantity management on dedicated "My Cellar" page. Auto-remove when quantity hits 0. Cellar data feeds back into taste profile for richer signals.

- [ ] CellarEntry model + migration — user_id, sku (FK), quantity, added_at
- [ ] Cellar CRUD endpoints — add, list, update quantity, remove
- [ ] "Add to cellar" button on product cards
- [ ] My Cellar page — list with quantity +1/−1 controls
- [ ] Surface "In your cellar (×2)" on product cards in search results
- [ ] Remove bottle flow — "Tu l'as bue?" → journal prompt or just remove

Design reference: `ui/cellar/cellar.html`, `ui/cellar/add-bottle.html`, `ui/cellar/remove-bottle.html`

### Side Quests (not product phases)

Self-contained, user-facing additions that don't belong to a product phase. Can ship any time without blocking the roadmap.

#### Waitlist & Admin Panel

Replace invite codes with a waitlist + admin approval flow. Landing page collects email only. Admin approves in-app, Resend sends approval email with login link. Lays the foundation for the admin panel.

- [x] `POST /api/waitlist` — public endpoint, email only, silent 201 on duplicate, IP rate limited (#580)
- [x] Admin waitlist endpoints — list pending, approve, reject (#581)
- [x] Resend integration — approval email on approve, `email_sent_at` tracking, resend action (#582)
- [x] Frontend — landing page waitlist form, replace invite code input (#583)
- [x] Frontend — admin panel: pending queue, approve/reject, active users (#584)
- [ ] Remove invite codes — model, migration, repo, endpoints, frontend (#585)

#### Custom Email Domain

Add `contact@coupette.club` via Proton Mail custom domain (requires Proton Unlimited). After Waitlist & Admin Panel milestone.

- [ ] Add `coupette.club` as custom domain in Proton Mail dashboard
- [ ] Update MX records on Hetzner DNS
- [ ] Update `noreply@coupette.club` → `contact@coupette.club` as reply-to (optional)

#### Extended Auth — GitHub + Google OAuth

OAuth-only login (no email/password, no Telegram login). Clean multi-provider identity model, RFC 6749 + RFC 9700 compliant. Telegram stays as a notification channel (link from Settings). See `docs/decisions/0008-oauth2-security-design.md`.

**Identity model:**

- `oauth_accounts` — `(provider, provider_user_id)` unique, links to `users.id`
- `users.email` — NOT NULL, always from OAuth provider (lowercased), secondary merge key
- `users.telegram_id` — nullable, notification channel only (not an auth credential)
- `users.display_name` — user-set at first login
- Login flow: find by `(provider, provider_user_id)` → find by email (auto-merge) → 403 if pending/rejected/unknown

**Security:** PKCE (S256) + AES-256-GCM encrypted + HMAC-SHA256 signed state + Redis single-use nonce.

- [ ] `oauth_accounts` table + `email` / `display_name` on `users` + backfill migration (#586)
- [ ] `OAuthAccount` repository — `find_by_provider`, `find_by_email`, `create`, `list_by_user` (#587)
- [ ] JWT refactor — drop `telegram_id` claim, add `display_name`, update frontend callers (#588)
- [ ] Redis setup — async client, state storage helpers (#589)
- [ ] GitHub OAuth — `/api/auth/github` + `/api/auth/github/callback`, PKCE + encrypted state (#590)
- [ ] Google OAuth — `/api/auth/google` + `/api/auth/google/callback`, same pattern (#591)
- [ ] Display name collection on first login (#592)
- [ ] Update bot `/api/auth/telegram/check` — query via `oauth_accounts` (#593)
- [ ] Linked Accounts API — list, disconnect (last-provider guard), link Telegram (#594)
- [ ] Frontend — GitHub + Google login buttons, `/auth/callback` route (#595)
- [ ] Frontend — Settings: Linked Accounts section (#596)
- [ ] Account deletion — `DELETE /api/users/me` + cascade (#597)
- [ ] Remove `ADMIN_TELEGRAM_ID` + remaining invite code auth logic (#598)
- [ ] CSP headers (infra) + rate limiting on OAuth + waitlist endpoints (#599)

#### MCP Server / Sonnet + Tools

Dev tooling project — expose Coupette data to Claude Code / Claude Desktop via MCP. Same tool architecture as intent router but different transport. Not user-facing.

- [ ] Tool schema definitions — `search_wines()`, `get_product()`, `get_user_watches()`
- [ ] Agentic tool execution loop — Claude calls tools, backend executes, returns results
- [ ] MCP server entry point for Claude Code / Claude Desktop
- [ ] Pipeline benchmark — side-by-side quality comparison: Haiku RAG vs Sonnet + tools

### Ideas (unscoped)

- [ ] Usage & model controls — Sonnet vs Haiku toggle in UI, per-user API cost tracking, monthly usage limits
- [ ] Wine lists — named collections ("BBQ wines"), shareable via public link
- [ ] "Drink tonight" — context-aware quick pick from cellar ("I'm making lamb, what should I open?")
- [ ] "My Year in Wine" — annual recap (total tasted, avg score, top region, highest-rated, shareable)
- [ ] Chat-driven journal entry — log tastings via conversation ("just had the Mont-Redon, solid 88")
- [ ] Rating aggregator — enrich products with Vivino scores and critic ratings; fuzzy name matching
- [ ] Price comparison vs France — compare SAQ prices to French retail (Wine-Searcher, Vinatis)
- [ ] Chrome extension — floating "Watch" button on SAQ product pages (reuses bot URL paste SKU extraction logic)
- [x] Bilingual web app — FR/EN with react-i18next, ~90 strings, language switcher in sidebar
- [ ] Bilingual bot — per-user language preference, static translation tables, bilingual bot responses (#134, #151–#153)
- [ ] Wine tech sheets — external data enrichment beyond SAQ catalog (fiches techniques, critic notes)
- [ ] Bot `/recommend` deprecation — remove command, bot is alerts-only (cross-cutting chore, not a product idea)
- [ ] Data retention policy — define TTL for chat sessions, user data lifecycle, and compliance posture (GDPR-adjacent)
- [ ] Settings page — language, notifications, data export, account management (most items need backend work)
- [x] Sidebar collapse/expand — icon-only 60px sidebar with tooltips (#556)
- [ ] Notification panel — in-app availability alerts (currently Telegram-only)

---

## Cross-cutting

### UX Improvements

- [ ] Sidebar restructure — grouped nav (Discover / My Wines / My Stores) to scale for future phases
- [ ] Product card action overflow — expandable row for 3+ actions (Watch visible, tasting/cellar on expand) when tasting + cellar ship

### DevOps & CD Pipeline

**Production safety:**

- [x] Automated DB backups — weekly pg_dump + 30-day retention via systemd timer (#351)
- [x] Include alembic config in backend Docker image for in-container migrations (#227)

**CI hardening:**

- [x] Container security scan — Trivy on built images, catches OS-level CVEs that pip-audit misses (#360)

**CD pipeline:**

- [x] Build + Trivy + push to GHCR on tag push (#362)
- [x] docker-compose.prod.yml — GHCR images, restart policies, no dev volumes (#364)
- [x] Automated deploy on tag push (`deploy_frontend.sh` + `deploy_backend.sh` via SSH)
- [x] Auto-create GitHub Release with changelog on tag push
- [x] Production environment — GitHub Environment with main-only deployment branch policy, tag protection ruleset
- [x] Environment-scoped secrets — move deploy secrets from repo-level to production environment (prerequisite: automated CD or k3s migration)

Platform-level concerns (monitoring alerts, secrets management, IaC, staging, K8s) are tracked in the [infra ROADMAP](https://github.com/vpatrin/infra/blob/main/docs/ROADMAP.md). Engineering backlog (testing, observability, SRE) is tracked in [ENGINEERING.md](ENGINEERING.md#backlog).

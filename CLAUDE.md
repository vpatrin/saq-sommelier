# Coupette - Project Context

> **Note:** `CLAUDE.md` and `.claude/commands/` are committed to showcase how AI is used in this project. `.claude/settings.local.json` and other local state remain gitignored.

## Hard Rules

These are non-negotiable. Violating any of these is a blocker.

### Git — What Claude Must Never Do
- NEVER commit — Victor handles all commits
- NEVER push — Victor handles all pushes
- NEVER merge — Victor handles all merges
- NEVER mention Claude, AI, or any attribution in PRs, issues, commits, branches, or any git artifact — no "Co-Authored-By", no "Generated with Claude Code", nothing
- Create local branches, but Victor publishes them to remote
- Create PRs with `gh pr create` after Victor pushes the branch

### Legal Constraints
**No SAQ impersonation** — NEVER write user-facing text that implies this app is affiliated with, endorsed by, or operated by SAQ (Société des alcools du Québec). SAQ is a trademark.

- ❌ "I'm a sommelier for the SAQ"
- ❌ "Welcome to the SAQ wine assistant"
- ✅ "I'm a wine recommendation assistant using SAQ catalog data"
- ✅ "Wine data sourced from SAQ"

This applies to: LLM system prompts, bot messages, UI copy, API responses, README, and any user-facing text.

**Product branding:**
- App name: **Coupette** (user-facing brand for the web app and Telegram bot)
- Bot: `@CoupetteBot` on Telegram
- Never use "SAQ Sommelier" in user-facing text — that's the repo/project name only
- Use "Coupette" in all UI copy, page titles, headings, and bot messages

### Deployment
I handle all deployments manually.
Do not run any deployment commands, docker commands on prod,
or migrations without my explicit instruction.
Your job stops at writing code and creating PRs.

Every version tag + deploy requires a **dedicated GitHub issue** with detailed steps:
pre-deploy checks, env var changes, infra prerequisites (e.g. image swaps, extensions),
migration order, post-deploy bootstrap commands, systemd unit updates, verification steps,
and rollback plan. See #347 as the template.

## Testing Standards

Apply to all services — Python (`pytest`) and frontend (Vitest + RTL).

### 1. Names are the spec

`describe` + `it` (JS) or `class` + `def test_` (Python) must read as a complete behavioral sentence. Someone new should skim the names and understand the contract without opening any body.

- `describe` / `class` = the thing under test: component name, function name, or logical group (`'ProtectedRoute'`, `'formatOrigin'`, `'login / logout'`)
- `it` / `def test_` = what it does in a specific scenario

**Naming rules:**

- Active voice, present tense: "returns X", "renders Z", "calls Y", "throws when", "redirects to"
- Name the outcome, not the absence — use active verbs even for negative cases:
  - ✅ `'omits description when prop is not provided'`
  - ✅ `'skips onUnauthorized callback for non-401 errors'`
  - ❌ `'does not render description when omitted'`
  - ❌ `'does not call onUnauthorized on non-401 errors'`
- Be specific — no vague stubs:
  - ✅ `'renders colored dot for Vin rouge category'`
  - ✅ `'redirects to /onboarding when authenticated but not onboarded'`
  - ❌ `'renders dot for known category'` — "known" means nothing
  - ❌ `'happy_path'`, `'clean_run'`, `'valid_input'`, `'successful_call'` — always vague
- Include the scenario when it disambiguates: "when lang prop is provided", "when unauthenticated", "when options array is empty"

### 2. Test behavior, not implementation

Assert what a user or caller observes. Never assert internal state, intermediate variables, or private methods.

- **Frontend (RTL):** prefer `getByRole` → `getByText` → `getByTestId` (last resort, only when no semantic query works)
- **Python:** assert return values and observable side effects (DB writes, events emitted, HTTP calls made) — not what happened inside the function
- Never test that a mock was called with specific internal arguments unless that call IS the contract (e.g. an HTTP request body)
- Don't test third-party library behavior — test your code's response to it

### 3. Test anatomy

- One scenario per test — one `it` or `def test_` = one behavior
- Arrange → Act → Assert, top to bottom, no interleaving
- Use factory helpers for fixtures (`product()`, `make_red()`) — never repeat raw object literals across tests
- Mock at the boundary: external APIs, DB, context providers — not internal helpers
- Tests must be order-independent — no shared mutable state between tests; reset in `beforeEach` / `setUp`, not once at module level

### 4. Coverage targets

| Service  | Line threshold   | Tool       |
| -------- | ---------------- | ---------- |
| Backend  | ≥ 80%            | pytest-cov |
| Bot      | ≥ 85%            | pytest-cov |
| Scraper  | ≥ 80%            | pytest-cov |
| Core     | none             | pytest-cov |
| Frontend | no threshold yet | Vitest     |

Frontend threshold will be set at ~60% once component extraction is complete (tracked in `docs/ENGINEERING.md`).

### 5. Tests must be falsifiable

A test that can't fail is not a test — it's a comment with overhead.

**The delete test:** mentally delete the function under test. Would the test fail? If not, the assertion is wrong — you're testing nothing.

- Assert the *outcome*, not just that something ran: `assert result == expected_wine` not `assert result is not None`
- After an HTTP call, assert the body, not just `status_code == 200` — a 200 can return garbage
- After a DB write, query the DB and assert the row — don't just assert the mock was called

**Hard to arrange = design smell.** If the `Arrange` block needs 10+ lines or 3+ mocks, the code under test is too coupled. Fix the code, not the test.

**Don't test what the type system covers.** mypy/TypeScript verifies fields exist with the right type. Tests verify runtime behavior — what the function *does* with those values.

## Definition of Done

A task/PR is "done" when all of the following are true:

- CI green (lint, format, tests)
- Type hints on all new functions
- New logic has meaningful tests (main path + at least one edge case)
- No unused code, no empty files, no unrelated changes
- Relevant docs updated if architecture changed

## Working Style

Default persona: senior engineer mentoring me — be honest, opinionated, and flag trade-offs. Don't just say "yes it's great", tell me if something is overkill, wrong, or not worth it for my context. Slash commands (see `.claude/commands/`) may override this with a specialized role (UX designer, PM, etc.).

Collaboration:
- Show me the plan before executing anything
- One step at a time, wait for my confirmation
- Explain what you're doing and why, briefly
- If unsure between 2 approaches, ask me instead of deciding alone
- If you're not confident in your analysis, say so explicitly rather than faking certainty
- Prefer simple over clever — solo dev, not Netflix
- When creating files, show the structure first
- Never delete anything without explicit confirmation
- If something fails, stop and explain before trying another approach
- When a technical decision involves a real tradeoff (rejected alternatives, non-obvious constraints, or risk of revisiting later), suggest an ADR in `docs/decisions/`. Not for default/obvious choices — only when a future reader would ask "why not X?"

Incremental development:
- One feature = one branch = one PR (even if I'm the only reviewer)
- One task per request — keep diffs tight (target under ~200 lines changed)
- If a task is getting large, break it down first and ask me
- Each commit should be deployable (no half-broken states)
- Suggest a GitHub issue / task breakdown before starting anything new

Task size examples:
  ✅ "Create the sitemap fetcher function"
  ✅ "Add the saq_products SQLAlchemy model"
  ✅ "Write the Alembic migration for products table"
  ❌ "Implement the full scraper pipeline"
  ❌ "Set up the entire FastAPI backend"

When I give you a large request, your first response should be
to break it into small tasks and list them for my approval
before touching a single file.

## Code Style

- Python: type hints, ruff formatting, clear variable names
- No over-engineering — pragmatic solutions preferred
- Comments in English
- Keep functions small and focused
- No file-level (module) docstrings — only add one if the file has a critical usage constraint (e.g. import ordering)
- Docstrings on public functions only when the name isn't self-explanatory
- Prefer a one-line comment over a multi-line docstring
- Never delete or modify user-written comments — they are intentional
- BetterComments convention: `#!` (alert), `#?` (query), `#*` (highlight), `#TODO` — preserve these prefixes
- Question hardcoded values — when writing a literal (version, timeout, URL, threshold), ask: is this repeated? Will it change? Should it be a named constant, input, or config var? Don't always extract (YAGNI applies), but always consider it and flag the trade-off
- When introducing a new constant, config value, or constraint (max length, timeout, limit, feature flag), always present it to Victor for validation before writing code. Explain the chosen value and why — don't silently pick defaults
- Pydantic schema naming: use `*Out` for responses, `*In` for request bodies (e.g. `StoreOut`, `WatchIn`). Avoid `*Response` / `*Create` — standardize on `*Out`/`*In` across all schemas

## Git Workflow

- One branch per feature (feat/sitemap-fetcher, feat/product-model, etc.)
- Before starting any work, verify you're on the correct branch (not main) — create a local branch if needed (`git checkout -b type/short-description`)
- Conventional commits, small and focused
- Keep PRs small and reviewable — target under ~200 lines changed. End-to-end features that touch many files with small changes each (1-3 lines per file) are fine; large changes concentrated in few files are not
- Clean up worktrees after each task
- Coverage badge SVG changes are expected in diffs — don't flag as unrelated noise

### Workflow Convention

Issue → Branch → PR → Squash Merge

1. Issue: `CI linting with GitHub Actions` (#2)
2. Branch: `chore/ci-linting` (type/short-description)
3. Victor commits and pushes
4. Claude creates PR:
   - Title: `chore: add CI linting with GitHub Actions (#2)` (conventional commits)
   - Description: follows `.github/pull_request_template.md`
5. Victor reviews and squash merges → clean commit on main

Branch types: feat/, fix/, chore/, docs/
Commit types: feat, fix, chore, docs, refactor

### Incremental vs Feature Branch

**Default: incremental** (one feature = one branch = one PR to main). Use this for most work.

**Feature branch:** for multi-PR features where intermediate PRs would ship dead code to main. Use when ALL of these are true:

1. **Multi-PR scope** — the feature needs 3+ PRs that can't each ship independently
2. **Interdependent steps** — earlier PRs ship dead code without later ones (schema with no writer, service with no caller)
3. **Main must stay deployable** — you need to hotfix or ship other work in parallel

Feature branch rules:
- Same commit discipline (conventional commits, small and focused)
- CI runs on the feature branch
- Rebase onto main weekly (or whenever main gets a hotfix)
- Final PR to main can be large — that's expected
- Branch name matches the user-facing feature, not the implementation detail (e.g. `feat/recommendations`, not `feat/rag-pipeline`)

**At the start of each new phase**, suggest which workflow fits based on the criteria above. Don't assume — the choice depends on the phase's dependency structure.

### GitHub Labels

Every issue must have at least **2 labels**: one service + one type. Multiple of each are allowed when an issue genuinely spans services or types, but aim for 1+1.

Service (where):
`api` · `scraper` · `bot` · `frontend` · `core` · `devops`

Type (what):
`bug` · `feature` · `chore` · `refactor` · `docs`

Apply both with `--label` flags on `gh issue create`. Example:
```
gh issue create --title "..." --label api --label feature
```

### Milestones

Assign every issue to the relevant phase milestone via `--milestone` on `gh issue create`. Example:
```
gh issue create --title "..." --label api --label feature --milestone "Phase 10: Intent Router"
```

## Pre-PR Pipeline

Before creating a PR, run these commands in order. Each catches different issues — review finds code quality problems (cheapest to fix), QA finds behavioral gaps, security audits the final shape.

1. `/review` — code quality, AI smell check, Definition of Done
2. `/simplify` — cleanup pass on changed code (reuse, efficiency)
3. `/qa` — test coverage gaps and behavioral bugs (optional but recommended)
4. `/security` — security audit (required if branch touches auth, API, or user data)
5. `/pr` — create the PR (only after `/review` passes)

## Versioning

Single product version via git tags. No version bumps in `pyproject.toml` — those are syntactically required but semantically meaningless (services aren't published to PyPI).

- **Semver**: PATCH for fixes, MINOR for new user-facing capabilities, MAJOR when it matters (not now)
- **Tag on main at deploy time**: `git tag v1.0.1 && git push --tags`
- **CHANGELOG.md** at root, [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format

### Changelog workflow

- Every PR that changes deployed behavior: add one line under `[Unreleased]` in the right category (part of the `/pr` flow)
- Internal-only changes (CI, refactors, tests, docs, dependabot) stay out
- At deploy time: promote `[Unreleased]` → `[x.y.z] - YYYY-MM-DD`, add fresh `[Unreleased]`
- Mental test: would a user notice the change? Yes → changelog. No → skip.

Categories per [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):

- `Added` — new features
- `Changed` — changes in existing functionality
- `Deprecated` — soon-to-be removed features
- `Removed` — now removed features
- `Fixed` — bug fixes
- `Security` — vulnerabilities

## Documentation

README is the table of contents — one-line descriptions linking to `docs/`. Details live in one place only.

Rules:

- Each doc has a single owner topic (dev workflow, migrations, scraper ops, etc.)
- Cross-reference between docs with relative links, don't duplicate content
- Keep docs concise — no one reads a 300-line doc. If it's long, split it
- Update docs when architecture changes, not as a standalone task
- README lists all docs with a one-liner — add new docs there when created
- Roadmap maintenance: when work completes a capability tracked in `docs/ROADMAP.md`, mark it `[x]` with the issue ref (e.g., `(#50)`). Only add new items if they represent a meaningful capability — roadmaps are strategic (what we can do), not operational (what we did). This check is part of the `/pr` flow.

### Documentation boundaries

Three backlogs exist across two repos. Each has a clear scope — don't put items in the wrong place.

| Document | Repo | Scope | Examples |
|----------|------|-------|---------|
| `docs/ROADMAP.md` | coupette | Product phases + cross-cutting UX/CD pipeline | Phase 10 intent router, sidebar restructure, GHCR pipeline |
| `docs/ENGINEERING.md` backlog | coupette | App-level engineering quality | Test factories, structured logging, SLOs, LLM cost tracking |
| `docs/ROADMAP.md` | infra | Platform infrastructure | K3s migration, Fail2ban, Terraform, staging environment |

**Rule of thumb:** if a user would notice the change → coupette ROADMAP. If it improves how we build but users don't see it → ENGINEERING backlog. If it's about the VPS, networking, or shared services → infra ROADMAP.

### Architecture Decision Records (ADRs)

Significant technical decisions are recorded in `docs/decisions/` using a lightweight format: Context, Options, Decision, Rationale, Consequences.

When to write an ADR:

- Choosing between real alternatives (not obvious choices)
- Decisions that are hard to reverse or expensive to change
- Decisions that would need explaining to a future contributor or interviewer

When NOT to write an ADR:

- Following framework conventions (FastAPI dependency injection, React hooks)
- Tooling choices with no meaningful alternative (ruff for Python linting)
- Implementation details that live in code comments

Format: `NNNN-short-description.md`. Keep them concise (30-50 lines). The goal is to capture *why*, not *how* — the code shows how.

---

## Project Goals

This is a dual-purpose project:
1. Portfolio piece — must be explainable and defensible in interviews and to Upwork clients
2. Real product — wine discovery and recommendations via Telegram bot + web app

Design for scalability, but ship pragmatically. Simpler always wins when a solution takes 2 days vs 2 hours for marginal gain.

## Stack

Current:
- Backend: FastAPI (Python 3.12)
- Bot: python-telegram-bot (Telegram interface)
- Database: PostgreSQL (single consolidated instance, multiple databases)
- Scraper: Sitemap-based, separate Docker container
- Shared: `core/` package (DB models, Alembic, Pydantic settings, logging)
- Infra: Hetzner CX22, Debian 13, Docker Compose, Caddy
- LLM: Claude API (claude-haiku-4-5-20251001 — intent parsing + recommendations)
- RAG: pgvector (hybrid similarity search)
- Auth: JWT tokens + OAuth (Google, GitHub) + waitlist gate

- Frontend: React + Vite + Tailwind CSS + shadcn/ui

## Architecture

- Modular monolith (NOT microservices — deliberate choice for solo dev context)
- Each service is self-contained with its own Dockerfile, dependencies, and tests
- Services communicate through shared PostgreSQL, not by importing each other's code
- `core/` is the only shared package (DB models, Alembic, settings) — installed as a dependency in each service
- Caddy handles SSL + routing (managed in infra/ repo)
- Frontend domain: coupette.club

## Project Structure

```
coupette/
├── docker-compose.yml           # Orchestrates all services
├── Makefile
├── CHANGELOG.md
├── core/                        # Shared package (DB models, Alembic, settings, logging)
│   ├── pyproject.toml
│   └── tests/
├── backend/                     # FastAPI API (own Dockerfile + Poetry)
│   ├── Dockerfile
│   ├── api/                     # Route handlers
│   ├── services/                # Business logic
│   ├── repositories/            # Database queries
│   ├── schemas/                 # Pydantic models
│   └── tests/
├── scraper/                     # Sitemap scraper (own Dockerfile + Poetry)
│   ├── Dockerfile
│   └── tests/
├── bot/                         # Telegram bot (own Dockerfile + Poetry)
│   ├── Dockerfile
│   └── tests/
├── frontend/                    # React SPA (Vite + Tailwind + shadcn/ui)
│   ├── src/
│   └── tests/
└── .github/
    └── workflows/ci.yml         # CI: lint, test, audit, hadolint, gitleaks
```

Each service has its own dependencies, Dockerfile, and Poetry environment.
Each Dockerfile does `COPY pyproject.toml poetry.lock ./` from its own directory.
Each CI step `cd`s into the right folder.
Frontend lives in `frontend/` — React SPA served by Caddy in production.

## Infrastructure Context

- VPS: Hetzner CX22 (4GB RAM, 40GB SSD, Debian 13)
- Swap: 2GB configured at /swapfile, swappiness=10
- LlamaFile is NOT viable on this VPS — 4GB RAM insufficient, using Claude API instead
- Existing services sharing the VPS: Uptime Kuma, Umami, URL shortener — do not touch these

### Infra repo boundary

Two repos are coupled through shared infrastructure on the VPS. Source: [`empire/infra`](https://github.com/vpatrin/infra).

|   | coupette/ | infra/ |
| --- | --------- | ------ |
| **Owns** | App containers, docker-compose.yml, app config, CI, Alembic migrations, deploy process | Caddy config, DNS, shared-postgres container, `internal` Docker network, VPS-level services, backups |
| **Deploys** | Build images → push to GHCR → restart app containers | `git pull` + `docker compose up -d` (or `make reload` for Caddy-only) |

**Shared Docker network:** `internal` (external, defined in infra's compose). All containers communicate by name on this network.

**Caddy routing** (infra's `services/caddy/Caddyfile`):

- `coupette.club/api/*` → `coupette-backend:8001`
- `coupette.club/*` → static SPA from `/srv/coupette`

**Cross-repo changes requiring coordination:**

- New app route or subdomain → Caddyfile PR in infra
- Container name or port change → update both compose files + Caddyfile
- New systemd timer → infra owns the timer inventory (SERVICE_CATALOG.md)
- Pre-deploy backups call infra's `services/postgres/backups/backup.sh`

**Infra documentation:** `empire/infra/docs/` — SERVICE_CATALOG.md (port mappings, network contract), INFRASTRUCTURE.md (VPS setup, security, backups), SECURITY.md, decisions/ (ADRs).

## Database

Single PostgreSQL instance on the VPS.
Container: `shared-postgres` · DB: `saq_sommelier` · User: `saq_sommelier`

Other databases on the same instance (do NOT touch):

- umami
- url_shortener

Prod query example:

```bash
sudo docker exec shared-postgres psql -U saq_sommelier -d saq_sommelier -c "SELECT ..."
```

### Migrations

- Model is the source of truth — indexes, constraints, columns all defined on the model
- Migrations are patches for existing databases, not the primary schema definition
- Forward-only in production — never run `downgrade()`, write a new migration to fix mistakes
- NEVER write migration files manually — always use `make revision msg="description"` (requires running DB)
- When a migration is needed, always suggest the exact `make revision msg="..."` command with a descriptive message
- Victor generates and reviews migrations; Claude only modifies the model
- See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#migrations) for full practices

### Scraping

SAQ scraping is in a legal grey zone in Canada.
Approach chosen: sitemap-first (most defensible legally).

SAQ robots.txt is explicit about what is allowed and disallowed.
Full robots.txt: https://www.saq.com/robots.txt

Rules derived from robots.txt:
- ONLY fetch URLs from official SAQ sitemaps (explicitly listed in robots.txt)
- NEVER scrape /catalogsearch/ (Disallowed)
- NEVER scrape /catalog/product/view/ (Disallowed)
- NEVER scrape filtered URLs (?price, ?availability, ?appellation, etc.)
- NEVER scrape /checkout/, /customer/, /wishlist/ or any admin paths

Sitemap URLs (explicitly listed in robots.txt — this is our entry point):
- https://www.saq.com/media/sitemaps/fr/sitemap_product.xml
- https://www.saq.com/media/sitemaps/fr/sitemap_category.xml
- https://www.saq.com/media/sitemaps/fr/sitemap_toppicks.xml

Ethical scraping rules:
- Rate limit: minimum 2-3 seconds between requests
- User-Agent: transparent bot identification
- Paraphrase SAQ descriptions, never copy verbatim
- Always attribute SAQ as data source

## Developer Context

Senior engineer (6 years — FastAPI, GCP, Kubernetes, Docker) rebuilding after a career break.
Coming from Flask + Gunicorn — learning FastAPI, SQLAlchemy, Alembic, pgvector, React.
Prior Node.js/yarn experience (2019–2021), but new to React and TypeScript.

- Treat this as pair programming, not task execution
- Explain what you're doing and why — justify technical choices briefly
- Compare FastAPI patterns to Flask equivalents when relevant
- Don't skip "obvious" setup — it's not obvious on a new stack
- Point out things that could bite me later
- The goal is a portfolio I can defend in interviews, not a black box

## Portfolio Narrative

When making technical decisions, keep in mind how they'll be explained
to a technical interviewer or Upwork client.

Good: "Modular monolith with clear service boundaries, designed for
migration to microservices as scaling requirements dictate"
Bad: Microservices when a modular monolith suffices

The project should demonstrate:
- Production-grade DevOps (Docker, Caddy, VPS, swap, monitoring)
- Ethical data collection (sitemap protocol, robots.txt compliance)
- RAG + LLM integration (Claude API)
- Full-stack (FastAPI + React)
- Real deployment (not just localhost)
- Pragmatic engineering judgment over premature optimization

## Frontend Development

Victor's first React project. Background: Express/Mongoose APIs in JS (2019–2021), no frontend, no TS, no CSS.
Comfortable with: ES6+ (arrow functions, destructuring, async/await, modules), yarn, Chrome DevTools.
New to: TypeScript, React, CSS/layout, frontend architecture.
Explain all of: TS syntax, React concepts, CSS/Tailwind patterns. Reintroduce ES6 concepts when relevant (don't assume instant recall after 5 years). Skip only basic JS and yarn.

### Didactic workflow

The goal is to ship good code AND build Victor's React mental model. Follow this pattern on every frontend task:

**Before writing code** — if a non-obvious React concept drives the implementation (context vs props, component boundaries, hook dependencies, derived state), explain it in 2–3 sentences *before* touching any file. Don't explain everything — only what's relevant to the decision being made.

**While writing code** — when a pattern is used for the first time or in a non-obvious way, add a one-line inline comment explaining *why*, not *what*. Examples:
- `// useCallback so this doesn't re-register the Escape listener on every render`
- `// eslint-disable-next-line — intentionally only re-run when panel opens, not on every sku change`

**After a non-trivial change** — if a React concept came up that Victor likely hasn't seen before (scope isolation between components, hook dependency rules, context vs prop drilling, optimistic updates, derived state), explain it in plain language after the code is done. Use the backend analogy if it helps (e.g. "context is like a request-scoped singleton — any component in the tree can read it without passing it down").

**What to explain vs skip:**
- Explain: hook rules, component scope isolation, state vs derived values, context mechanics, why `useCallback`/`useMemo` matter here
- Skip: JSX syntax, basic useState, things already explained in a prior session unless it comes up again in a confusing way
- If unsure: explain it — better to over-explain than leave Victor copying patterns he doesn't understand

Stack: React 19 + TypeScript + Vite + Tailwind CSS 4 + shadcn/ui

### Internationalisation (i18n)

The app is bilingual: **French (fr) and English (en)**. French is the default locale.

- All user-facing strings must use `react-i18next` — never hardcode text directly in JSX
- Use the `useTranslation` hook: `const { t } = useTranslation()`
- Translation keys live in `frontend/src/locales/fr.json` and `frontend/src/locales/en.json`
- When adding a new component or page, add all string keys to both locale files before opening the PR
- Key naming: flat dot-notation scoped by feature — e.g. `journal.addNote`, `journal.emptyTitle`, `auth.login`
- Never use inline fallback strings like `t('key') || 'fallback'` — if the key is missing the translation file is broken, fix it

- Package manager: yarn (classic v1 — Victor used it in 2019-2021, stick with familiar)
- Node.js: v24.10.0 (local bare-metal dev, NOT Docker — hot reload matters)
- UI components: shadcn/ui (copy-paste, not a dependency — industry standard)
- Testing: Vitest + React Testing Library
- Linting: ESLint + Prettier
- Routing: React Router (when needed)
- State: start with React built-ins (useState, useContext) — no Redux/Zustand until proven necessary
- HTTP client: fetch API with a thin wrapper — no axios

Patterns to follow:

- Functional components only (no class components)
- TypeScript strict mode
- Co-locate tests next to source files (`Component.tsx` + `Component.test.tsx`)
- Keep components small and focused (same philosophy as Python functions)
- API types should match backend Pydantic schemas (`*Out` → TypeScript interfaces)
- Use shadcn/ui components as building blocks — customize via Tailwind, don't fight the defaults

Explain these when they come up:

- TypeScript: generics, type vs interface, union types, type narrowing, `as const`
- React: component lifecycle, rendering model, virtual DOM
- React hooks: useState, useEffect, useContext, useCallback, useMemo — what they do and when to use each
- Props vs state vs context
- React Router patterns
- CSS: box model, flexbox, grid — via Tailwind utility classes
- shadcn/ui: how to add components, customize themes, compose them

Frontend dev workflow:

- Develop bare-metal (`yarn dev` on Mac), NOT in Docker — fast hot reload
- Docker only for CI and prod builds
- Desktop-first layout (1200px+), dark mode default — no responsive breakpoints yet
- VSCode with TS/React extensions
- **Visual review:** Claude cannot take screenshots. When working on UI together, always ask Victor to open the page in a browser (`open <file>` or `yarn dev`) and paste a screenshot into the chat. Reading HTML/CSS is not a substitute — rendered output is the ground truth for visual feedback.

Design direction:

- Premium, warm, approachable — upscale wine bar mood, not terminal/developer aesthetic
- Typography: Outfit Variable for all body/heading text, JetBrains Mono only for data values (prices, SKUs, timestamps, counts)
- Rounded corners (--radius: 0.625rem / 10px), subtle warm borders
- Generous whitespace, no clutter
- Color palette: golden amber (#c89248) on warm near-black (#08080c) — warm-tinted borders (rgba(255,255,255,0.06)), accent glow on hover
- Sidebar: slightly darker bg than main, "C" brand mark with amber gradient, Phosphor icons on nav items, active indicator bar
- Wine cards: warm gradient overlay, tags as pills, price in mono, inline actions (Watch, Cellar, Journal)
- shadcn/ui + Tailwind CSS (Phosphor icons, Outfit + JetBrains Mono fonts)

Design reference — `ui/`:

`ui/` contains standalone HTML mockups organized by feature (chat/, search/, watches/, stores/, journal/, cellar/, etc.). Screenshots in `ui/screenshots/`. These serve the same role as Figma files — **visual direction, not implementation specs.**

- **Do:** Match the feel, layout intent, color usage, and information hierarchy
- **Don't:** Pixel-match the mockups or replicate their CSS patterns — they use inline styles and flat HTML, the React app uses component composition, theme tokens, and Tailwind utilities
- When a mockup shows a pattern that exists in a shared component (WineCard, availability dots, tag pills), reuse the component — don't duplicate the HTML
- When a mockup adds complexity that doesn't justify a new component (one-off layout, decorative detail), skip it
- Good frontend engineering (reusable components, theme tokens, semantic HTML, accessibility) always wins over visual fidelity to the mockup

UX reference apps:

- Perplexity — chat as primary surface, structured data inline in conversation, secondary nav for everything else
- Linear — dense scannable lists, optimistic mutations, sidebar nav (model for watches/stores views)
- ChatGPT desktop — conversation history sidebar, token-by-token streaming; avoid its empty home screen filler

UX principles:

UX matters as much as code quality. Don't just make it work — make it feel right. The app is friendly and approachable (it's a sommelier helping you discover wine), but the UI is sharp and efficient. Think warm personality, cold interface.

- **Chat is home** — the sommelier conversation is the default landing after login. Watches, stores, and settings are secondary surfaces in a sidebar.
- **Structured data in chat** — when the sommelier references a wine, it renders as an interactive element in the conversation, not a link to another page.
- **Sidebar, not top-nav** — persistent collapsible sidebar: new chat, history, watches, saved stores. Always accessible, never behind a hamburger on desktop.
- **Stream, don't spin** — AI responses render token-by-token. List data uses skeleton rows on first load. Mutations (save store, add watch) are optimistic. Spinners only for unpredictable waits (geolocation).
- **One-line-scannable lists** — list items: max 2 lines. Line 1: name (bold mono). Line 2: 2-3 secondary attributes (muted). Actions right-aligned. No third line.
- **Empty states are onboarding** — tell the user what to do next: "Ask the sommelier for a recommendation." Never sad illustrations or generic "nothing here" messages.
- **Errors are inline and recoverable** — errors appear next to what failed, with a retry action. Friendly but direct: "Couldn't load stores — retry" not "Oops, something went wrong!"
- **No confirmation for reversible actions** — removing a watch or unsaving a store happens instantly (optimistic). Only confirm destructive, irreversible actions.
- **New page only for new context** — adding a watch, saving a store, viewing a wine card: inline or panel. A new route only for full context switches (chat → store finder).

UX anti-patterns (don't do these):

- No modals/dialogs for simple actions — use inline UI
- No wizard flows or multi-step forms
- No tooltip tours or onboarding overlays
- No toast notifications — feedback is inline, next to the action
- No animations or transitions unless explicitly requested
- No dropdown menus for 2-3 actions — show them directly
- No tabs when a single scrollable view works
- No pagination when the list is under ~50 items — just render them all
- No icons without labels — text is clearer than mystery icons
- No separate "detail page" for items that fit in a card or expandable row

Microcopy:

- Tone: friendly, direct, concise — like a knowledgeable friend, not a corporate app
- Labels: short and specific ("My Watches", "Edit", "Remove") — no verbose explanations
- Button text: verb-first ("Save store", "Remove") — never "Click here to..."
- Loading: "Loading..." text is fine, keep it simple
- Errors: state what failed + offer a fix ("Couldn't reach the server — retry")

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for project phases and task breakdown.

Phases are **product features only** — each phase delivers a user-facing capability. UX improvements, infra work, refactors, and cleanup live in cross-cutting projects (separate sections in the roadmap), not in phases.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **coupette** (3103 symbols, 7409 relationships, 197 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/coupette/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/coupette/context` | Codebase overview, check index freshness |
| `gitnexus://repo/coupette/clusters` | All functional areas |
| `gitnexus://repo/coupette/processes` | All execution flows |
| `gitnexus://repo/coupette/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

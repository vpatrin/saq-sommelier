# ADR 0006: React + shadcn/ui for Frontend

**Date:** 2026-03-10
**Status:** Accepted

## Context

Coupette needs a web frontend for features that don't fit the Telegram bot UX (search with filters, chat interface, store management). The developer has backend experience (FastAPI, Flask, Express) and prior JavaScript/Node.js experience (2019–2021) but no React, TypeScript, or CSS experience.

## Options considered

1. **Next.js** — full-stack React framework, SSR, file-based routing, API routes.
2. **React + Vite** — SPA, client-side rendering, fast HMR, minimal framework opinions.
3. **HTMX + Jinja** — server-rendered with sprinkles of interactivity, no JS framework.
4. **Vue + Nuxt** — similar to React/Next but different ecosystem.

## Decision

Option 2: React 19 + Vite + TypeScript + Tailwind CSS 4 + shadcn/ui. SPA served as static files by Caddy, API calls to the FastAPI backend.

## Rationale

- **React is the industry standard.** Portfolio value matters — React is what hiring managers and clients expect. Vue or HTMX would need justification in interviews.
- **Vite over Next.js.** The app is a pure SPA — no SEO requirements (wine recommendations behind auth), no server-side rendering needed. Next.js would add a Node.js server to the production stack (currently Python-only) for features we don't use. Vite gives fast HMR and zero runtime overhead.
- **shadcn/ui over building from scratch.** Copy-paste component library (not a dependency) gives production-quality UI primitives without learning CSS from scratch. Components are customizable via Tailwind — no fighting a design system.
- **TypeScript strict mode.** Catches bugs at compile time that a backend engineer would otherwise discover at runtime. Worth the learning curve.
- **Tailwind over vanilla CSS.** Utility-first approach avoids the cascade and specificity issues that trip up CSS beginners. Co-located with components, not in separate files.

## Consequences

- **Learning curve is real.** React hooks, TypeScript generics, component lifecycle, and CSS layout are all new. Development is slower initially but builds transferable skills.
- **No SSR means no SEO.** Fine for an authenticated app. If a public marketing page is needed later, it can be a static page served by Caddy — no framework change required.
- **Frontend runs bare-metal in dev** (`yarn dev`), not in Docker. Hot reload speed matters for learning — Docker adds too much latency for iterative CSS/component work.
- **Caddy serves the built SPA in production** — no Node.js process to manage. The frontend is just static files after `yarn build`.

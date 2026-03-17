# ADR 0001: Modular Monolith Over Microservices

**Date:** 2026-01-15
**Status:** Accepted

## Context

Coupette has multiple services (API, bot, scraper, frontend) that could be architected as microservices or as a monolith. We're a solo developer serving ~20 users on a single VPS (Hetzner CX22, 4GB RAM).

## Options considered

1. **Microservices** — each service communicates via HTTP/gRPC, owns its database, deployed independently with service mesh.
2. **Traditional monolith** — single codebase, single deployment, shared everything.
3. **Modular monolith** — separate codebases with independent Dockerfiles and dependencies, communicating through a shared PostgreSQL database. No cross-imports between services.

## Decision

Option 3: modular monolith. Services share PostgreSQL but never import each other's code. Each has its own `pyproject.toml`, Dockerfile, and test suite.

## Rationale

- **Microservices are premature.** Service mesh, API gateways, distributed tracing, and per-service databases add operational overhead that doesn't pay off with 1 developer and 20 users. The complexity would consume more time than it saves.
- **Pure monolith is too coupled.** With a single codebase, the scraper (batch job) and backend (API server) would share dependencies, deployment lifecycle, and failure domains. The scraper crashing shouldn't take down the API.
- **Modular monolith gives service independence without operational overhead.** Each service can be restarted, scaled, or replaced independently. PostgreSQL as the integration layer means no message queues, no event buses — just tables.

## Consequences

- Adding a new service requires only a new directory with its own Dockerfile — no infrastructure changes.
- All services must agree on the database schema (managed via `core/` shared package with SQLAlchemy models and Alembic migrations).
- Horizontal scaling is limited to running multiple instances of the same service behind a load balancer. Cross-service scaling (e.g., scaling the API without the scraper) is already possible since they're separate containers.
- Migration to microservices is possible later by replacing PostgreSQL reads with API calls — the service boundaries are already clean.

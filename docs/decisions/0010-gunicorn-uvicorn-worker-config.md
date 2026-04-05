# ADR 0010: Gunicorn + UvicornWorker for Production Server

**Date:** 2026-04-05
**Status:** Accepted

## Context

The backend was running bare `uvicorn` in production — a single process with no supervision. A crash brings the service down until Docker restarts the container. On a CX22 (2 vCPU, 4GB RAM) shared with Postgres, bot, scraper, and several other services, we need process supervision and multi-core utilization without over-provisioning.

## Options considered

1. **Bare Uvicorn** — single process, no supervision, single core.
2. **Uvicorn `--workers N`** — built-in multi-process mode, no external dependency, but newer and less battle-tested than Gunicorn for process lifecycle management.
3. **Gunicorn + UvicornWorker** — Gunicorn manages processes (20 years of production hardening), each worker runs a Uvicorn ASGI event loop.

## Decision

Gunicorn with `UvicornWorker`, 2 workers, `--timeout 120`, `--graceful-timeout 30`.

## Rationale

- Gunicorn handles process supervision, graceful restarts on deploy, and SIGTERM correctly — Uvicorn's multi-worker mode is newer and less proven for this.
- 2 workers utilizes both CX22 CPU cores; the app is I/O-bound (LLM calls, DB queries) so each async worker handles high concurrency without needing more processes.
- Worker count is deliberately below the `2×CPUs+1` formula (which would give 5) — the CX22 runs multiple shared services and RAM headroom matters more than theoretical throughput at current traffic.
- `--timeout 120` prevents Gunicorn from killing workers mid-LLM-call (Claude API responses can take 30–60s).

## Consequences

- Gunicorn added as a production dependency.
- In-memory rate limiting (SlowAPI) is now split across 2 processes — each worker has its own counter. Acceptable at current scale; will be fixed by the Redis backend introduced in the same branch.
- Bump workers to 3 when RAM usage allows headroom; re-evaluate at CX32 upgrade (formula: `2×CPUs+1`).

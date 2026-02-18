# Testing Roadmap

Part of the [project roadmap](../ROADMAP.md). Multi-layer test strategy: unit → integration → contract → ML → e2e.

## Phase 1 — Unit Tests (~2 days)

- [ ] Test infrastructure — conftest files, pytest markers (unit/integration/ml/slow), pyproject.toml config
- [x] Scraper unit tests — parser, sitemap fetcher + saved HTML fixtures (#20)
- [ ] Backend unit tests — scoring service, guardrails, LLM service (mocked Claude)
- [ ] Bot unit tests — handlers (mocked Telegram), formatters

## Phase 2 — Integration Tests (~1.5 days)

- [ ] Test database setup — docker-compose.test.yml with PostgreSQL on RAM disk (tmpfs)
- [ ] Seeded fixtures — 3-10 realistic products covering red, white, spirit
- [ ] Repository integration tests — search, filter, pagination, upsert, idempotency
- [ ] API integration tests — endpoints, validation errors, health checks

## Phase 3 — ML Tests (~1 day)

- [ ] Embedding tests — dimensions, normalization, similarity sanity checks
- [ ] Retrieval quality tests — category accuracy, price compliance, bilingual overlap
- [ ] Guardrail edge cases — prompt injection, hallucination detection, parametrized valid/invalid queries

## Phase 4 — Contract Tests (~half day)

- [ ] API response schema validation — Pydantic models against real responses
- [ ] Bot API client contract — verify bot's assumptions about API shape

## Phase 5 — End-to-End Tests (~1 day)

- [ ] E2E fixture — docker-compose spins up full stack, waits for healthy
- [ ] User journey tests — browse → search → detail, recommend → verify wines exist
- [ ] Graceful degradation tests — search works without ChromaDB, recommend degrades without Claude

## Phase 6 — CI Integration (~half day)

- [x] Unit tests on every PR (#2, #72, #73)
- [x] Coverage thresholds per service — 90/75/75 in pyproject.toml (#62)
- [x] Coverage thresholds enforced in CI (#125)
- [ ] ML eval on PRs labeled `ml`

## Phase 7 — Test Culture (ongoing)

- [ ] docs/TESTING.md — coverage targets, classification table, bug-to-test rule
- [ ] Product factory (`tests/fixtures/factory.py`) — `make_red()`, `make_white()`, `make_wines(n)`

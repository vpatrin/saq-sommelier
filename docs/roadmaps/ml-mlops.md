# ML / MLOps Roadmap

Part of the [project roadmap](../ROADMAP.md). Embedding pipeline, RAG, evaluation framework, and production ML practices.

## Phase 6a — Embeddings (~2 days)

- [ ] ChromaDB service in docker-compose, `core/db/chroma.py` client
- [ ] `core/db/embeddings.py` — all-MiniLM-L6-v2, composite text builder
- [ ] `scraper/src/embed_sync.py` — post-scrape embedding pipeline
- [ ] Embedding eval checkpoint — hit rate, MRR, bilingual overlap
  - Decision gate: bilingual overlap < 50% → swap to multilingual-MiniLM

## Phase 6b — Claude Integration (~3 days)

- [ ] `backend/services/llm_service.py` — Claude Haiku wrapper with tool use
- [ ] `backend/services/rag_service.py` — 4-stage pipeline (parse → retrieve → recommend → validate)
- [ ] `backend/services/rag_config.py` — versioned prompt/threshold config
- [ ] `backend/services/guardrails.py` — input validation, hallucination prevention

## Phase 6c — Bot Integration (~2 days)

- [ ] `/recommend` handler wired to RAG pipeline
- [ ] Conversation memory — `conversations` + `messages` tables, last 10 to Claude

## Phase 6d — MLOps Foundation (~3 days)

- [ ] LLM call logging → PostgreSQL (function, model, tokens, cost, latency)
- [ ] Full RAG eval — automated checks + LLM-as-judge scoring
- [ ] User feedback loop — 👍👎 buttons → `recommendation_feedback` table
- [ ] Trace logging — full pipeline state per recommendation for reproducibility

## Phase 7 — ML Optimization (~4 days)

- [ ] HyDE for vague queries (hypothetical document embedding)
- [ ] Prompt caching for system prompts
- [ ] Semantic caching — second ChromaDB collection for query deduplication
- [ ] Eval in CI — quick (10 queries) on PR, full (50+) weekly

## Phase 8 — Advanced ML (~5 days, only if eval data justifies)

- [ ] Model comparison framework (`ml/compare_models.py`)
- [ ] Fine-tune embedding model with bilingual wine pairs
- [ ] Wine label scanner (Claude Vision)
- [ ] A/B testing prompts with tracked metrics

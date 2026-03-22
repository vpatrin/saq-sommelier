# ADR 0005: RAG Pipeline Architecture

**Date:** 2026-03-07
**Status:** Accepted

## Context

Coupette needs natural language wine recommendations ("a bold red under $25 for pasta night"). This requires understanding user intent, searching a catalog of ~14k wines, and presenting curated results with explanations. The system runs on a 4GB VPS alongside PostgreSQL + pgvector.

## Options considered

1. **Keyword search + manual filters** — SQL full-text search with user-selected facets (category, price, country). No LLM. Simple but can't handle natural language queries or nuanced intent.
2. **Vector search + LLM curation** — embed products, similarity search, LLM explains results. Handles natural language but no structured filtering (price, category) without post-filtering.
3. **RAG pipeline: intent parsing → hybrid retrieval → diversity reranking → curation** — LLM extracts structured filters from natural language, hybrid query combines vector similarity with SQL filters, reranking ensures diversity, LLM curates explanations.

## Decision

Option 3: RAG pipeline with five stages.

| Stage | Tool | What it does |
| --- | --- | --- |
| Intent parsing | Claude Haiku (`tool_use`) | Extracts structured filters (categories, price range, country, grapes, exclude) from natural language |
| Query embedding | OpenAI `text-embedding-3-large` (1536-d) | Converts the semantic query into a vector for similarity search |
| Hybrid retrieval | pgvector + SQL | Vector similarity filtered by intent (category, price, country, availability). Over-fetches 5× candidates |
| Diversity reranking | Python (MMR-style) | Greedy selection with redundancy penalty — avoids 5 wines from the same producer/grape |
| Curation | Claude Haiku (`tool_use`) | Per-wine explanations and a selection summary, returned as structured JSON |

Multi-turn context: sliding window of last 5 turns. Previously recommended SKUs excluded from future results within a session.

## Rationale

- **pgvector over Pinecone/Weaviate.** Hybrid queries (vector similarity + SQL filters) in a single statement. No extra service competing for 4GB RAM. 14k vectors fit in memory; exact scan is fast enough without a vector index. Backups and migrations already cover PostgreSQL.
- **text-embedding-3-large over 3-small.** Upgraded from `3-small` for better bilingual FR/EN retrieval quality. Same 1536-d (Matryoshka truncated), same storage — strictly better vectors for ~2× cost per token. Model-aware content hashing ensures embeddings regenerate on model change.
- **Claude Haiku over Sonnet.** Intent parsing is structured extraction — Haiku is reliable and fast (~1s). Curation is template-bounded. Cost: ~$0.60/month vs. ~$3/month. Latency: ~1s vs. 3-5s. Sonnet upgrade is a config change if needed.
- **Intent as structured extraction, not classification.** `tool_use` (forced function calling) extracts typed fields (categories, price range, grapes, semantic query) — handles compound queries naturally and fails gracefully.
- **MMR diversity reranking over naive top-k.** Pure similarity returns 5 wines from the same producer. Greedy selection with redundancy penalty (λ=0.5) balances relevance vs. diversity. Simple Python, no extra dependency.
- **Sliding window over summarization.** Last 5 turns in context — simple, predictable token budget. Previously recommended SKUs tracked across full session regardless of window.
- **LLM-as-judge eval.** Claude scores recommendations against a rubric (relevance, diversity, explanation quality). Runs on saved logs — dev/CI tool, not in the request path.

## Consequences

- Two external API dependencies in the hot path (Claude + OpenAI). Graceful degradation: API errors return a degraded response, never crash.
- Embedding updates are batch (scraper `embed-sync`), not real-time. New products are unsearchable by vector until next embed run.
- Haiku quality ceiling — if recommendations need deeper reasoning, Sonnet upgrade or hybrid approach available.
- Reranking adds latency (~50ms) but dramatically improves perceived quality.

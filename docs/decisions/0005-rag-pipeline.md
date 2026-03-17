# ADR 0005: RAG Pipeline Architecture

**Date:** 2026-03-07
**Status:** Accepted

## Context

Coupette needs natural language wine recommendations ("a bold red under $25 for pasta night"). This requires understanding user intent, searching a catalog of ~14k wines, and presenting curated results with explanations. The system runs on a 4GB VPS alongside PostgreSQL + pgvector.

## Decision

RAG pipeline with five stages: intent parsing → query embedding → hybrid retrieval → diversity reranking → curation. All vector storage in pgvector (PostgreSQL extension). Claude Haiku for LLM calls. OpenAI `text-embedding-3-large` for embeddings. LLM-as-judge eval framework for quality measurement.

## Architecture

| Stage | Tool | What it does |
|-------|------|--------------|
| Intent parsing | Claude Haiku (`tool_use`) | Extracts structured filters (categories, price range, country, grapes, exclude) from natural language |
| Query embedding | OpenAI `text-embedding-3-large` (1536-d) | Converts the semantic query portion into a vector for similarity search |
| Hybrid retrieval | pgvector + SQL | Vector similarity search filtered by intent (category, price, country, availability). Over-fetches 5× candidates |
| Diversity reranking | Python (MMR-style) | Greedy selection with redundancy penalty — avoids 5 wines from the same producer/grape |
| Curation | Claude Haiku (`tool_use`) | Per-wine explanations and a selection summary, returned as structured JSON |

Multi-turn context: sliding window of last 5 turns. Previously recommended SKUs excluded from future results within a session.

## Key choices and rationale

**pgvector over Pinecone/Weaviate.** Hybrid queries (vector similarity + SQL filters for price, category, country, availability) in a single statement. No extra service competing for 4GB RAM. No vendor lock-in. 14k vectors fit in memory; exact scan is fast enough without a vector index (IVFFlat or HNSW available when scaling requires it). Backups and migrations already cover PostgreSQL.

**text-embedding-3-large over 3-small.** Started with `text-embedding-3-small` (1536-d), upgraded to `text-embedding-3-large` (1536-d, Matryoshka truncated) for better bilingual FR/EN retrieval quality. Same dimension count, same storage — strictly better vectors for ~2× cost per token. Model-aware content hashing ensures embeddings regenerate on model change.

**Claude Haiku over Sonnet.** Intent parsing is structured extraction via `tool_use` — Haiku is reliable and fast (~1s). Curation is template-bounded — Haiku produces good output within constraints. Cost: ~$0.60/month at 20 users vs. ~$3/month for Sonnet. Latency: ~1s vs. 3-5s. Sonnet upgrade is a config change if quality proves insufficient.

**Intent as structured extraction, not classification.** Using `tool_use` (forced function calling) rather than few-shot classification. The LLM extracts typed fields (categories, price range, grapes, semantic query) — not just a label. This handles compound queries ("a bold red under $25, no merlot") naturally and fails gracefully (malformed intent → fallback, not crash).

**MMR diversity reranking over naive top-k.** Pure vector similarity returns 5 wines from the same producer. Greedy selection with a redundancy penalty (λ=0.5) balances relevance vs. producer/region diversity. Simple Python implementation, no extra dependency.

**Sliding window over summarization.** Last 5 turns (10 messages) kept in context. Simple, predictable token budget. Semantic summarization would preserve more context but adds an LLM call per turn and complexity. Previously recommended SKUs are tracked across the full session regardless of window.

**LLM-as-judge eval.** Claude scores recommendations against a configurable rubric (relevance, diversity, explanation quality). Runs on saved recommendation logs. No real-time overhead — eval is a dev/CI tool, not in the request path.

## Consequences

- Two external API dependencies in the hot path (Claude + OpenAI). Graceful degradation: API errors return a degraded response, never crash.
- Embedding updates are batch (scraper `embed-sync`), not real-time. New products are unsearchable by vector until next embed run.
- Haiku quality ceiling — if recommendations need deeper reasoning (food pairing, occasion matching), Sonnet upgrade or hybrid approach available.
- Reranking adds latency (~50ms) but dramatically improves perceived quality.

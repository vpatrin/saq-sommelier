# MCP Server — Spec

Phase 7. Exposes the SAQ catalog as an MCP tool server, enabling Claude to query wines directly.

Cross-references: [ROADMAP.md](../ROADMAP.md) Phase 7, [RECOMMENDATIONS.md](RECOMMENDATIONS.md) (current RAG pipeline this could replace).

---

## Why

The current recommendation pipeline (Phase 6) uses Haiku for intent parsing + pgvector retrieval + prompt-based curation. It works, but Claude already knows wine — it doesn't need a prompt chain to be a sommelier. An MCP server lets Claude query the catalog directly and apply its own knowledge.

This was identified during eval framework development: building an eval to score pipeline quality raises the question of why not let a stronger model drive the pipeline directly.

---

## Architecture Comparison

### Current (Phase 6)

```
User → Haiku (intent parsing) → pgvector → raw results → Haiku (curation) → response
```

- Haiku parses intent into structured filters
- pgvector retrieves candidates
- Haiku curates from candidates
- Pipeline quality depends on prompt engineering + eval iteration

### Proposed (Phase 7)

```
User → Sonnet/Claude (with tools) → pgvector → Sonnet curates with wine knowledge → response
```

- Claude parses intent natively (no schema needed)
- Claude calls `search_wines()` tool → pgvector similarity search
- Claude curates using its own wine expertise
- No intent parser, no eval framework, no pipeline optimization

---

## What the MCP Server Exposes

```
Tools:
├── search_wines(query, category?, country?, min_price?, max_price?, available_only?, limit?)
│   → pgvector similarity search with optional filters
│   → returns: name, price, country, region, grape, taste_tag, rating, sku, availability
│
├── get_product(sku)
│   → full product detail for a specific wine
│
├── list_categories()
│   → available wine categories with counts
│
└── get_catalog_stats()
    → total products, countries, price range, last scrape date
```

The tool implementations reuse existing repository code (`find_similar()`, product queries). The MCP server is a thin transport layer, not new business logic.

---

## Two Transports, Same Tools

**MCP protocol** — for developer use (Claude Code, Claude Desktop):
- Local stdio or SSE transport
- To explore the catalog conversationally
- Debug recommendations, understand data gaps, test queries

**Claude API + tool use** — for the web app:
- Same tool definitions, exposed as Claude API tools
- React frontend sends user query → thin backend calls Claude API with tools → Claude queries DB → response
- One `/chat` endpoint replaces the current recommendation service

```
┌─────────────┐     ┌──────────────┐
│ Claude Code  │────▶│              │
│ Claude Desktop│    │  MCP Server  │──▶ PostgreSQL + pgvector
└─────────────┘     │  (tools)     │
                    └──────┬───────┘
                           │ same tool logic
┌─────────────┐     ┌──────┴───────┐
│ React App   │────▶│ /chat endpoint│──▶ Claude API + tools ──▶ DB
└─────────────┘     └──────────────┘
```

---

## Trade-offs vs Current Pipeline

| Dimension | Phase 6 (Haiku + RAG) | Phase 7 (Sonnet + tools) |
|---|---|---|
| Recommendation quality | Limited by prompt engineering | Claude's full wine knowledge |
| Cost per query | ~$0.002 (Haiku) | ~$0.01-0.03 (Sonnet) |
| Latency | ~500ms | ~2-5s |
| Determinism | Same query → same results | May vary |
| Debuggability | Inspectable intent + SQL | Black box |
| Code complexity | 10+ files (intent, retrieval, eval) | 1 endpoint + tool defs |
| Caching | Trivial (deterministic) | Harder (non-deterministic) |
| Vendor lock-in | Moderate (embeddings portable) | High (Claude is the brain) |

**Verdict:** Phase 7 is better for quality and simplicity. Phase 6 is better for cost and control. Both can coexist — fast deterministic search for browse/filter, Claude-powered `/chat` for natural language.

---

## What Survives from Phase 6

- **Scraper** — data collection unchanged
- **Embeddings + pgvector** — MCP tools use the same vector search
- **Retrieval query** (`find_similar()`) — reused as tool implementation
- **Watches + alerts** — push-based, MCP can't replace (MCP is pull-based)
- **Bot notifications** — Telegram push for restocks/delists stays

**What becomes unnecessary:**
- Intent parsing service (`backend/services/intent.py`)
- Recommendation service orchestration (`backend/services/recommendations.py`)
- Eval framework (`backend/eval/`) — Claude's curation doesn't need scoring
- Rubric, queries.json, levers.md — optimizing a pipeline that no longer exists

---

## Impact on Backend

With MCP + Claude API driving recommendations, the backend shrinks:

**Keeps:**
- Watches CRUD (or exposed as MCP tools)
- Availability checker cron job
- Store endpoints

**Removes:**
- `/recommend` endpoint
- Intent parsing
- Recommendation service
- Eval framework

**Adds:**
- `/chat` endpoint (thin Claude API proxy with tool definitions)
- MCP server entry point

The REST API stays relevant for the React frontend's non-conversational features (browse, filter, product detail, watches). The `/chat` endpoint handles natural language.

---

## Portfolio Narrative

Two complementary stories:

1. **Phase 6 (shipped):** "I built a RAG pipeline with intent parsing, pgvector retrieval, and an LLM-as-judge eval framework. Here's how I measured and improved recommendation quality."

2. **Phase 7 (evolution):** "Then I realized Claude with direct tool access gives better recommendations with 10x less code. I built an MCP server and a `/chat` endpoint. Here are the trade-off numbers."

The transition from Phase 6 → 7 demonstrates architectural judgment — knowing when to simplify, not just when to build.

---

## Implementation Order

1. MCP server with `search_wines()` + `get_product()` (dev tool, immediate value)
2. Test MCP via Claude Code/Desktop — validate quality vs current pipeline
3. `/chat` endpoint with Claude API + same tool definitions
4. React frontend with chat interface
5. Deprecate intent parsing + recommendation service (keep eval for comparison data)

---

## Open Questions

1. **Coexistence vs replacement.** Keep Phase 6 pipeline for deterministic search alongside Phase 7 chat? Or fully replace?
2. **Cost management.** Sonnet at scale — budget caps, caching strategies, model selection per query complexity?
3. **Conversation state.** MCP is stateless. Multi-turn chat ("something like that but cheaper") needs session management in the `/chat` endpoint.
4. **Personalization.** Watch history as implicit taste signal — inject into Claude's context or as a tool (`get_user_preferences`)?

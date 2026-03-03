# AI RAG — Phase 6 Architecture Spec

Phase 6 builds the RAG + Claude infrastructure. Client integration (bot `/recommend`, weekly digest) is Phase 6b and depends on this layer being stable first.
This spec locks in architectural decisions before any code is written.

Cross-references: [ROADMAP.md Phase 6](../ROADMAP.md), [ENGINEERING.md ML/MLOps](../ENGINEERING.md), [TELEGRAM_BOT.md](TELEGRAM_BOT.md)

---

## Decisions already made

| Decision | Choice | Rationale |
| --- | --- | --- |
| Embedding model | `all-MiniLM-L6-v2` (sentence-transformers) | Fast, small (80MB), good English quality; see [Bilingual risk](#bilingual-risk) |
| LLM | `claude-haiku-4-5-20251001` | ~$0.002/call, fast, sufficient for recommendation text |
| Vector store | ChromaDB (embedded, same container as backend) | ~38k products is tiny; one less container |
| Pattern | RAG context injection, not tool use | Simpler, more predictable for `/recommend` |

---

## Embedding pipeline

**When:** Triggered via `--embed-sync` CLI flag on the scraper (same pattern as `--scrape-stores`). Run post-scrape in the weekly systemd timer, or standalone for a full rebuild.
Lazy-on-query creates latency spikes and is harder to reason about.

**Incremental strategy:**

- Track `embedded_at` per product (compare against `updated_at`)
- Embed only products where `updated_at > embedded_at` (new + changed)
- Delete ChromaDB entries for delisted products
- `make embed-reset` for full rebuild (model upgrade, schema change)

**Composite text** — fields that capture what the wine IS, not just its name:

```text
{name} · {category} · {country} · {region} · {description}
```

Example: `Château Margaux 2018 · Vin rouge · France · Bordeaux / Médoc · Élégant et structuré, ce vin...`

Price and availability are NOT in the embedding text — they go in metadata for pre-filtering (see below). Embedding price into text would conflate semantic similarity with price proximity.

### Bilingual risk

The SAQ catalog is in French. `all-MiniLM-L6-v2` is English-dominant. Users may query in either language.

Eval checkpoint: after initial embed, run 20 representative queries in both FR and EN and compare result overlap. If FR/EN retrieval overlap < 50%, swap to `paraphrase-multilingual-MiniLM-L12-v2` (same API, broader language support, slightly larger).

---

## ChromaDB setup

**Deployment:** embedded inside the backend container (no separate service).
Volume mount: `/data/chroma` → persists across `docker compose down`.

**Collection: `wines`**

```python
# Document (what gets embedded):
text = f"{name} · {category} · {country} · {region} · {description}"

# Metadata (for pre-filtering, not embedded):
metadata = {
    "sku": str,          # FK to products.sku
    "name": str,
    "price": float,      # for price range filters
    "category": str,     # "Vin rouge", "Vin blanc", etc.
    "country": str,
    "available": bool,   # updated post-scrape
    "url": str,
}
```

One collection. No partitioning needed at this scale.

---

## Retrieval strategy

**Hybrid:** ChromaDB metadata filter → semantic rank within that subset.

```text
User: "un rouge fruité autour de 25$"
→ Parse intent: category=rouge, price_max=35, available=true
→ ChromaDB query with where={"category": "Vin rouge", "price": {"$lte": 35}, "available": True}
→ Top-k=10 semantic matches returned
→ Pass to Claude
```

ChromaDB's `where` clause handles both filtering and ranking in a single call — no SQL pre-filter needed. The metadata stored in ChromaDB is sufficient.

**Top-k = 10** — gives Claude enough diversity without bloating the prompt.

### Intent parsing

A lightweight parser extracts structured filters from the user query before the ChromaDB call. Start simple:

- Category keywords: rouge, blanc, rosé, bulles, mousseux, whisky, etc.
- Price signals: "autour de 25$", "moins de 40$", "budget 50$"
- Availability: default to `available=True` unless user asks about unavailable wines

No LLM needed for this step — regex + keyword matching is sufficient for the MVP. Upgrade to structured extraction (Claude tool use) only if intent parsing fails too often.

---

## Claude integration

**Pattern: RAG context injection** — retrieve top-k wines, inject as structured text into Claude's prompt, Claude writes the recommendation.

Tool use (letting Claude call catalog APIs directly) adds latency and non-determinism. Reserve it for future features like `/versus` or `/occasion` where Claude needs multiple targeted lookups.

### Prompt structure

```text
System:
You are a sommelier at the SAQ (Société des alcools du Québec).
Recommend wines ONLY from the catalog below. Never invent a wine or a detail.
If no wine fits, say so — don't hallucinate.
Respond in the same language as the user's question.

Catalog ({n} wines):
[1] {name} — {price}$ — {country}, {region}
    {description_excerpt}
    SKU: {sku}
...

User: {query}
```

### Guardrails

1. **Prompt constraint:** "only from the catalog below" — primary defense
2. **Post-response SKU validation:** extract any SKU Claude mentions, verify it exists in PostgreSQL. If missing → retry without that SKU, or surface "no exact match, here are alternatives"
3. **Graceful degradation:** if ChromaDB unavailable → fall back to SQL-only results with no LLM text (see [Graceful degradation](#graceful-degradation))

No hallucination is truly impossible, but the catalog injection + validation loop catches the most common failure mode (invented wine names).

---

## Conversation memory

**MVP: in-memory only** — store last 3 turns in `context.user_data` (python-telegram-bot).

- No DB table needed at 20 users
- Resets on bot restart (acceptable; bot restarts weekly for updates)
- 3 turns ≈ 300 tokens of history — enough for "suggest something else" follow-ups

**Upgrade trigger:** add `conversations` + `messages` tables when:

- Conversation state needs to survive restarts, OR
- A feature requires persistent taste history (e.g., `/cellar`, `/taste-profile`)

Not now (YAGNI).

---

## Token budget

Per `/recommend` call with top-k=10:

| Component | Tokens |
| --- | --- |
| System prompt | ~200 |
| 10 wine cards | ~500 |
| 3-turn history | ~300 |
| User query | ~50 |
| **Total input** | **~1,050** |
| Claude output | ~300 |

At Haiku 4.5 pricing ($0.80/MTok in, $4.00/MTok out):

- Input: ~$0.00084
- Output: ~$0.0012
- **~$0.002 per call**

At 20 users × 10 queries/day = $0.40/day = ~$12/month. Negligible.

**Caching:** not needed at this scale. If the same user sends the same query within 1h, that's edge-case noise. Implement only if costs spike unexpectedly.

**Daily budget cap:** set `CLAUDE_DAILY_BUDGET_USD` env var + track token usage in a lightweight counter. Alert via Telegram DM when 80% consumed. Prevents runaway costs from bugs.

---

## Graceful degradation

```text
/recommend request
  │
  ├─ ChromaDB available?
  │     ├─ YES: retrieve top-k → Claude → natural language response
  │     └─ NO:  → SQL top results + "AI unavailable, here are some matches" message
  │
  └─ Claude available?
        ├─ YES: full RAG response
        └─ NO:  → SQL top results + "AI unavailable" message
```

Three levels: full RAG → SQL + message → error. The bot always returns something useful.

---

## Implementation order

Phase 6 is the RAG infrastructure. Client integration (bot `/recommend`, weekly digest) is Phase 6b and depends on the RAG layer being stable first.

**Phase 6a — RAG infrastructure:**

1. `--embed-sync` CLI flag on the scraper — ChromaDB setup + incremental embedding (#154), same pattern as `--scrape-stores`
2. Bilingual eval checkpoint — run before wiring Claude; verify FR/EN retrieval quality
3. `backend/services/rag_service.py` — retrieval + intent parsing (#155)
4. `backend/services/claude_service.py` — prompt builder + guardrails (#155)
5. `GET /api/recommendations` endpoint — wraps rag_service + claude_service
6. LLM cost logging → `recommendation_log` table (query, tokens_in, tokens_out, latency)

**Phase 6b — Client integration:**

1. Bot `/recommend` handler (#156) — calls endpoint, renders response
2. `👍👎` feedback buttons → `recommendation_feedback` table
3. Weekly digest via Claude — LLM-curated summary after scraper run (#120)

# ADR 0007: Sommelier Memory Architecture

**Date:** 2026-04-01
**Status:** Accepted

## Context

The Coupette sommelier is stateless — every query starts from zero knowledge of the user. It knows the catalog but nothing about the person asking. Recommendations improve with context ("you love Rhône Syrah, your budget is $25–35") but that context must currently be re-stated every session. As Journal, Cellar, Watches, and Search accumulate real user data, there is an opportunity to build a longitudinal user model that makes the sommelier meaningfully better over time — without the user doing anything explicitly.

The core problem: LLMs have no memory between sessions. The solution space ranges from naive (inject full chat history) to sophisticated (distilled, structured, continuously updated user model). The choice has implications for cost, quality, and complexity.

Note: the Claude API provides raw model inference only. Memory, Projects, and persistent context are Claude.ai product features — they are not available via API. This architecture builds an equivalent system purpose-built for Coupette, with richer signal sources and domain-specific synthesis.

## Options considered

1. **Full conversation history injection** — load all past sessions into context at query time. Simple to implement, token limits hit fast, costs scale linearly with usage, no synthesis — the model gets raw history not understanding.

2. **Vector memory (MemGPT-style)** — embed all past interactions, retrieve relevant memories at query time via similarity search. Handles scale but retrieval quality is unpredictable, adds latency, requires another vector store, and retrieved fragments lack the coherence of a synthesized portrait.

3. **Static user preferences table** — DB columns for preferred regions, grapes, price range. Fast, queryable, but requires explicit user input, doesn't capture nuance, avoidances, context-switching, or evolving tastes. A form, not a memory.

4. **Distilled living documents — reflection-based memory** — compress raw signals (conversations, ratings, behaviour) into structured markdown profile files that grow richer over time. A capable model periodically synthesizes all signals into an updated portrait. Injected selectively at query time.

## Decision

Option 4: reflection-based memory using structured markdown documents, a two-tier extraction pipeline (Haiku for prose, SQL for behaviour), and a Sonnet overseer that synthesizes signals into an evolving user profile.

**Storage schema:**

| Table | Purpose |
|-------|---------|
| `user_signals` | Append-only log of extracted signals with source, timestamp, confidence |
| `user_profiles` | Four text columns per user — `palate`, `context`, `intent`, `behavior` — Sonnet-written markdown |
| `profile_update_jobs` | Debounce queue — one pending job per user, `run_after` timestamp |

**Four profile documents (stored as text columns in `user_profiles`):**

| File | Content | Cap |
|------|---------|-----|
| `palate` | Confirmed preferences, avoidances, nuance, score calibration | 500 words |
| `context` | Occasions, meals, household, language, buying-for-others | 250 words |
| `intent` | Exploring, aspirational wines, budget trajectory, confirmed vs. wished | 250 words |
| `behavior` | App usage patterns, recommendation acceptance, session habits | 200 words |

**Signal extraction — two paths, no overlap:**

- **SQL aggregation (free):** ratings, rebuy rate, price distribution, top regions/grapes, cellar breakdown, watch conversion rate, search funnel. Runs on every profile update. No model.
- **Haiku extraction (prose only):** runs once per closed chat session and once per tasting note with free-text. Extracts avoidances, occasion signals, curiosity signals, budget anchors, contradiction flags from unstructured text. ~$0.001 per trigger.

**Sonnet overseer:**

Runs nightly (or on debounced queue flush, whichever comes first). Reads all `user_signals` since last update + current `user_profiles` + SQL-derived stats. Writes updated profile documents. Does not query the DB directly — the job assembles pre-digested context. ~$0.05 per run.

**Trigger inventory:**

Every feature produces signals automatically:

| Feature | Trigger | Signal source |
|---------|---------|--------------|
| Chat session closes | new session started or 30min idle | Haiku extraction |
| Tasting note added | post-save | Haiku extraction (if notes/pairing non-empty) |
| Wine rated | post-save | SQL |
| Cellar entry added/removed | post-save | SQL |
| Watch added/fired | post-save | SQL |
| Search query | debounced | SQL |
| Recommendation accepted/skipped | post-action | SQL |
| Explicit feedback ("did that work?") | post-action | SQL |

All triggers call `enqueue_profile_update(user_id, delay=5min)`. Rapid events debounce into one Sonnet call.

**Context injection at query time:**

Profile files injected selectively based on intent router output:

```python
PROFILE_FILES_BY_INTENT = {
    "recommendation": ["palate", "context", "intent"],
    "wine_chat":      ["palate"],
    "pairing":        ["palate", "context"],
    "exploring":      ["palate", "intent"],
    "off_topic":      [],
}
```

Total injected context: ~1,200 tokens. Wrapped in `<user_profile>` tags, positioned after system prompt and before RAG results.

**Memory quality mechanisms:**

- **Confidence scoring:** each signal carries `evidence_count` and `sources`. Sonnet promotes entries from "signal" to "confirmed" at 3+ data points.
- **Signal decay:** signals include timestamps. Sonnet prompt explicitly instructs: discount signals older than 6 months when they conflict with recent ones.
- **Contradiction detection:** Sonnet flags contradictions rather than silently overwriting — preserved as `## Contradictions to monitor` entries with context (e.g. "asked for oaky Chardonnay despite avoidance — likely gift context").
- **Shared context:** `context` document includes a "People they buy for" section — preferences of others extracted from conversation ("my dad likes Bordeaux").
- **Explicit feedback loop:** post-recommendation "did that work out?" response is the highest-quality signal. Stored as `source='feedback'` with full context.

**Cold start:** onboarding handled as a conversational exchange (not a form) — sommelier asks 3 questions on first session, Haiku seeds initial `palate` and `context` documents. Generic behavior until first session closes.

## Rationale

- **Markdown over DB columns for profile content.** The profile is prose with structure, not structured data with prose. Markdown is the natural format — it's what the LLM writes, what gets injected into context, and what users see in the taste profile page. Storing as text columns in Postgres gives DB reliability without imposing a schema on content that evolves with each Sonnet update.
- **Sonnet for synthesis, Haiku for extraction, SQL for behaviour.** Each tool does only what it's best at. SQL is faster and cheaper than any model for aggregation. Haiku is reliable for pattern extraction from short prose. Sonnet's reasoning ability is justified only for the synthesis step — reading across all signals and writing a coherent, nuanced portrait.
- **Append-only signals, overwrite profile.** `user_signals` is the audit trail — never modified, always growing. `user_profiles` is the current best understanding — always the latest Sonnet synthesis. This separation means you can rerun the overseer on the full signal history if the synthesis prompt improves.
- **Nightly batch over real-time synthesis.** A profile that updates overnight is plenty fresh for recommendation quality. Per-event Sonnet is 10–50× more expensive for no meaningful quality gain. The debounce queue handles bursty activity (adding 5 tasting notes at once = one Sonnet call).
- **Reflection-based over retrieval-based memory.** Vector retrieval of past conversation fragments is unpredictable — you don't know what gets retrieved or whether it's coherent. Furthermore, retrieved fragments lack synthesis: contradictions surface raw at every query and the model must re-reason them every time. A synthesized portrait is stable, predictable, and improves monotonically. The tradeoff is that specific episodic memories ("that bottle on Valentine's Day") are not retrievable — this is acceptable at this stage and addressed by the episodic layer below.
- **Living document over versioned snapshots.** The profile should get richer over time, not replaced. Each Sonnet update incorporates new signals while preserving existing understanding — the document accumulates nuance rather than resetting to a new snapshot. Git commit history provides the audit trail if needed.

## Consequences

- Every feature is now a signal source. New features get memory integration for free by writing to `user_signals` on their save events.
- The taste profile page is a rendered view of `user_profiles` + SQL aggregations — no separate computation. One endpoint, two sources.
- Cost is predictable: ~$0.05/user/night for active users, zero for inactive. 100 active users ≈ $5/month. Scales linearly.
- Haiku system prompt must be updated to inject `<user_profile>` block. `max_tokens` increased from 512 to 1,024 to give the sommelier room for personalized responses.
- Profile quality is only as good as the Sonnet synthesis prompt. Prompt changes require a re-run of the overseer on existing signals — possible because `user_signals` is append-only and complete.
- At ~10k users, git-per-user audit trail becomes impractical — migrate to `user_profiles_history` table with timestamped snapshots. The core architecture (markdown as text columns) is unchanged.
- The recommendation quality feedback loop closes for the first time: signal → profile → recommendation → feedback → signal. The system improves with use.
- **Episodic memory is explicitly deferred.** This architecture answers "who is this person" — a synthesized portrait. It does not answer "what happened on Valentine's Day" — specific retrievable moments. The natural complement is a `user_history` table: timestamped events (tasting notes, notable recommendations, explicit memories) stored as vector embeddings, retrieved by similarity at query time. The two layers are additive: profile provides coherent identity, history provides specific episodic recall. Designed for a future phase — `user_signals` already captures the raw material.

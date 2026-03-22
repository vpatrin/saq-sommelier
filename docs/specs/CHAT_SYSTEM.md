# Chat System

Multi-turn conversational wine assistant. Intent routing via Claude Haiku, hybrid search via pgvector, curation via Claude.

---

## Flow

```
User message → save to DB → extract multi-turn context → classify intent
  ├── recommendation → RAG pipeline → RecommendationOut (JSON) → save → return
  ├── wine_chat     → sommelier service → plain text → save → return
  └── off_topic     → static bilingual message → save → return
```

## Session Lifecycle

| Operation | Endpoint | Notes |
|---|---|---|
| Create | `POST /api/chat/sessions` | Title = first 50 chars of first message |
| List | `GET /api/chat/sessions?limit=20&offset=0` | Ordered by `updated_at DESC` |
| Get | `GET /api/chat/sessions/{id}` | Includes full message history |
| Rename | `PATCH /api/chat/sessions/{id}` | Title max 50 chars |
| Delete | `DELETE /api/chat/sessions/{id}` | Cascades to messages |
| Send | `POST /api/chat/sessions/{id}/messages` | Returns assistant response |

All operations check session ownership (`user_id` match).

## Message Storage

Messages stored in `chat_messages` table, indexed on `(session_id, created_at)`.

| Field | Type | Notes |
|---|---|---|
| `role` | str | `"user"` or `"assistant"` |
| `content` | text | Plain text (user/sommelier) or JSON (recommendations) |

**Serialization:** recommendation responses are stored as `RecommendationOut.model_dump_json()`. On retrieval, the API attempts `model_validate_json()` and falls back to raw text if deserialization fails (handles schema evolution).

## Multi-Turn Context

**Sliding window:** last `CONTEXT_WINDOW_TURNS` (5) exchange pairs = 10 messages max.

Two windows, two purposes:

| Window | Size | Used for |
|---|---|---|
| Last 2 turns (4 messages) | Small | Intent parsing — resolves follow-ups ("something lighter") |
| Full sliding window (10 messages) | Large | Recommendation curation — personalizes explanations |

**SKU deduplication:** all assistant messages in the session are scanned to extract previously recommended SKUs. These are excluded from subsequent searches so the same wine is never recommended twice in a session.

**Empty sessions:** conversation history coerced to `None` (not empty string) for fresh sessions.

## Intent Routing

Claude Haiku classifies each message into one of three intents using tool_use:

### search_wines (recommendation)

User wants product recommendations. Claude extracts structured filters:

| Filter | Type | Example |
|---|---|---|
| `categories` | list[str] | `["Vin rouge"]` |
| `min_price`, `max_price` | Decimal | `20.00`, `30.00` |
| `country` | str, nullable | `"France"` |
| `semantic_query` | str | `"bold tannic red for grilled steak"` |
| `exclude_grapes` | list[str] | `["Merlot"]` |

Key prompt rules:
- Always infer categories from context (food → wine type)
- Price heuristics: "autour de 25$" → ±20%, "moins de 30$" → max only
- `semantic_query` must include grape names (embeddings use them)
- `exclude_grapes` populated on fatigue cues ("tanné de", "tired of")

### wine_chat (sommelier)

General wine knowledge — grape info, region facts, food pairing, winemaking, comparisons. No product recommendations. Claude responds conversationally (2-4 paragraphs).

### off_topic

Non-wine queries. Returns static bilingual message: "I'm a wine assistant — I can't help with that."

### Fallback behavior

- API error → treat as `recommendation` with raw query
- No tool_use block in response → treat as `wine_chat`

## Recommendation Pipeline Integration

When intent is `recommendation`, the full RAG pipeline runs:

1. **Embed** query via OpenAI `text-embedding-3-large`
2. **Search** via `find_similar()` — pgvector hybrid search with intent filters
3. **Curate** via Claude — generates per-product reasons + summary
4. **Assemble** `RecommendationOut` with products, reasons, intent, summary

Conversation history (full window) passed to curation for personalized explanations. Excluded SKUs passed to search to avoid repeats.

## Conversation Starters

Shown on empty chat (frontend only):

- "A bold red under $30"
- "What pairs with lamb?"
- "What's the difference between Syrah and Shiraz?"
- "Explore wines from Argentina"

Rendered as clickable prompt chips. On click, submitted as a regular message.

## Config

| Constant | Value | Purpose |
|---|---|---|
| `CONTEXT_WINDOW_TURNS` | 5 | Sliding window size (pairs) |
| `MAX_CHAT_MESSAGE_LENGTH` | 2000 | Input validation |
| `SESSION_TITLE_MAX_LENGTH` | 50 | Auto-generated title limit |
| `HAIKU_TEMPERATURE` | 0.3 | Intent parsing temperature |
| `DEFAULT_RECOMMENDATION_LIMIT` | 5 | Max products per recommendation |
| `NON_WINE_MESSAGE` | bilingual string | Off-topic / fallback response |

## Design Constraints

- **Synchronous responses** — no SSE streaming. The full pipeline completes before the API returns. Frontend shows "Thinking..." while waiting.

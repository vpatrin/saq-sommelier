# Telegram Bot

## Why a bot?

SAQ.com already lets you browse, search, and filter wines. The bot's value is **proactive intelligence** — things SAQ doesn't do:

- Alert you when a watched wine goes out of stock or comes back
- Natural language wine recommendations via Claude RAG + pgvector
- Push a weekly digest of new arrivals and restocks to a group chat (planned)

Target audience: ~20 friends in a private group chat.

## Commands

| Command | Description | Example |
|---|---|---|
| `/recommend <query>` | Natural language wine recommendations | `/recommend bold red under 30$` |
| `/watch <sku or url>` | Get alerts for availability changes | `/watch 10327701` |
| `/unwatch <sku or url>` | Stop watching a wine | `/unwatch 10327701` |
| `/alerts` | List your watched wines with inline remove buttons | `/alerts` |
| `/mystores` | Manage preferred SAQ store locations (GPS-based) | `/mystores` |
| `/help` | List available commands | `/help` |

Pasting a SAQ product URL in chat triggers a "Watch this?" prompt automatically.
Deep links (`t.me/bot?start=watch_{sku}`) trigger watch directly.

## Availability model

Delisted products (removed from SAQ sitemap) are always excluded from the API.

`/watch` alerts on any availability change:

- **Out of stock** — `availability` flips from `True` to `False`
- **Online restock** — `availability` flips from `False` to `True` (back in stock)
- **In-store restock/destock** — stock change at user's preferred stores
- **Delist** — product removed from SAQ catalog entirely (watch auto-removed)

## Architecture

The bot is a separate service (`bot/`) that calls the FastAPI backend over HTTP. It does NOT access the database directly.

```
Telegram API → Bot service → FastAPI backend → PostgreSQL
```

Bot→backend auth via `X-Bot-Secret` header on notification endpoints.

## Stock event notifications (#138, #212)

Event-driven pub/sub pattern using PostgreSQL as the queue.

### Why event-driven?

Watches are static subscriptions. The scraper detects availability transitions during upsert (it has both old and new state). Recording these as immutable events decouples the producer (scraper) from the consumer (bot) — the scraper doesn't know or care who's watching.

### Data flow

```
Scraper upsert                        Bot JobQueue (periodic)
  │                                     │
  │ availability changed?               │ GET /watches/notifications
  │         │                           │         │
  │    INSERT stock_events              │    JOIN stock_events × watches
  │    (sku, available=True/False)      │    WHERE processed_at IS NULL
  │                                     │         │
  │                                     │    Send Telegram messages
  │                                     │         │
  │                                     │    POST /watches/notifications/ack
  │                                     │    (set processed_at = now)
```

### Schema: `stock_events`

| Column | Type | Notes |
|---|---|---|
| `id` | serial PK | |
| `sku` | FK → products | Which product changed |
| `available` | boolean | New state: `True` = restock, `False` = destock |
| `detected_at` | timestamptz | When scraper detected the change |
| `processed_at` | timestamptz NULL | When bot sent notifications (`NULL` = pending) |

### Design decisions

- **Restock + destock** — scraper emits events on both transitions: `False → True` (restock) and `True → False` (destock). Users get notified in both directions.
- **`processed_at` per-event, not per-user** — at 20 users, one event fans out to all watchers in a single pass. A per-user delivery table (`notifications(event_id, user_id, sent_at)`) would be needed at scale but is over-engineering now.
- **Bot polls via JobQueue** — the bot already runs 24/7. A periodic check every 6h is simpler than chaining a systemd unit after the scraper timer.
- **Periodic cleanup** — old processed events are purged to prevent table bloat (#158).

## API dependencies

Endpoints the bot needs from the backend:

| Bot feature | API endpoint | Status |
|---|---|---|
| `/recommend` | `POST /recommendations` | Done (#155, #156) |
| `/watch` | `POST /watches`, `DELETE /watches/{sku}` | Done (#101) |
| `/alerts` | `GET /watches?user_id=` | Done (#101) |
| Product lookup (URL paste) | `GET /products/{sku}` | Done (#34) |
| Stock alerts | `GET /watches/notifications`, `POST /watches/notifications/ack` | Done (#138, #212) |
| Stores | `GET /stores/nearby`, `GET/POST/DELETE /users/{id}/stores` | Done (#232) |

## What's NOT in scope (yet)

- **Weekly digest** (`/digest`) — LLM-curated summary posted to group chat (#120)
- **Auth** — 20 friends, private bot, not needed yet

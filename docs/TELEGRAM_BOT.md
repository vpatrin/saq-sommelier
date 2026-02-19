# Telegram Bot

## Why a bot?

SAQ.com already lets you browse, search, and filter wines. The bot's value is **proactive intelligence** — things SAQ doesn't do:

- Alert you when a watched wine goes out of stock or comes back
- Push a weekly digest of new arrivals and restocks to a group chat
- Discover wines randomly or by filters without opening a browser
- Eventually: natural language recommendations via Claude (Phase 6)

Target audience: ~20 friends in a private group chat.

## Commands

| Command | Description | Example |
|---|---|---|
| `/search <query>` | Search wines by name | `/search mouton cadet` |
| `/new` | Recently added or updated wines | `/new` → filter by type/price |
| `/random` | Random wine suggestion | `/random` → filter by type/price |
| `/watch <sku>` | Get alerts for availability changes | `/watch 10327701` |
| `/unwatch <sku>` | Stop watching a wine | `/unwatch 10327701` |
| `/alerts` | List your watched wines and their status | `/alerts` |
| `/help` | List available commands | `/help` |

## Filter flow

Commands like `/new`, `/random`, and `/search` present inline keyboard buttons to narrow results:

```
User: /new
Bot:  [Rouge] [Blanc] [Rosé] [Mousseux]
      [< 15$] [15-25$] [25-50$] [50$+]
User: taps [Rouge] then [15-25$]
Bot:  3 new reds under $25 this week:
      1. Mouton Cadet 2022 — 16.95$
      2. ...
```

Filter values (categories, price ranges) are populated dynamically from the catalog facets API endpoint — not hardcoded.

## Weekly digest

After the scraper runs (Monday 03:00), the bot proactively posts to the group chat:

- New wines added this week
- Restocks of previously unavailable or delisted wines

No command needed — it just shows up. Powered by the same data the scraper already collects.

## Availability model

Delisted products (removed from SAQ sitemap) are always excluded from the API. Online availability is an optional filter:

- `/search` — shows all products including out-of-stock, so users can find wines and set up alerts
- `/new`, `/random` — only available wines (`?available=true`), no point suggesting something you can't buy

`/watch` alerts on any availability change:

- **Out of stock** — `availability` flips from `True` to `False`
- **Online restock** — `availability` flips from `False` to `True` (back in stock)
- **Relist** — product reappears in the SAQ sitemap after being delisted

## Architecture

The bot is a separate service (`bot/`) that calls the FastAPI backend over HTTP. It does NOT access the database directly.

```
Telegram API → Bot service → FastAPI backend → PostgreSQL
```

No auth needed — the bot is the only API consumer for now. If/when the React dashboard is added, we'll revisit auth.

## Restock notifications (#138)

Event-driven pub/sub pattern using PostgreSQL as the queue.

### Why event-driven?

Watches are static subscriptions. The scraper detects availability transitions during upsert (it has both old and new state). Recording these as immutable events decouples the producer (scraper) from the consumer (bot) — the scraper doesn't know or care who's watching.

### Data flow

```
Scraper upsert                        Bot JobQueue (periodic)
  │                                     │
  │ old=False, new=True?                │ GET /watches/notifications
  │         │                           │         │
  │    INSERT restock_events            │    JOIN restock_events × watches
  │    (sku, available=True)            │    WHERE processed_at IS NULL
  │                                     │         │
  │                                     │    Send Telegram messages
  │                                     │         │
  │                                     │    POST /watches/notifications/ack
  │                                     │    (set processed_at = now)
```

### Schema: `restock_events`

| Column | Type | Notes |
|---|---|---|
| `id` | serial PK | |
| `sku` | FK → products | Which product changed |
| `available` | boolean | New state: `True` = restock, `False` = destock |
| `detected_at` | timestamptz | When scraper detected the change |
| `processed_at` | timestamptz NULL | When bot sent notifications (`NULL` = pending) |

### Design decisions

- **v1: restock only** — scraper only emits events when `available` flips `False → True`. Users watch products because they want them back. Destock notifications can be added later without schema changes.
- **`processed_at` per-event, not per-user** — at 20 users, one event fans out to all watchers in a single pass. A per-user delivery table (`notifications(event_id, user_id, sent_at)`) would be needed at scale but is over-engineering now.
- **No `store_id`** — online availability only. In-store availability (Phase 5b) will use a separate `store_inventory` state table with its own event producer. The notification consumer (bot) stays the same.
- **Bot polls via JobQueue** — the bot already runs 24/7. A periodic check every 6h is simpler than chaining a systemd unit after the scraper timer.

### Task breakdown

| # | Task | Service | Depends on |
|---|------|---------|-----------|
| 1 | `RestockEvent` model + migration | core | — |
| 2 | Emit restock events during upsert | scraper | Task 1 |
| 3 | Pending notifications + ack endpoints | backend | Task 1 |
| 4 | Notification consumer (JobQueue) | bot | Task 3 |

### Future: in-store availability

In-store stock data lives in a separate `store_inventory` table (state, not events). When stock transitions from 0 → N at a store, that producer emits into the same notification pipeline. The bot consumer doesn't change — it just processes more events.

## API dependencies

Endpoints the bot needs from the backend:

| Bot feature | API endpoint | Status |
|---|---|---|
| `/search` | `GET /products?q=&category=&price_max=` | Done |
| `/new` | `GET /products?sort=recent` | Done (PR #107) |
| `/random` | `GET /products/random` | Done (PR #107) |
| Filter buttons | `GET /products/facets` | Done (#55, PR #105) |
| `/watch` | `POST /watches`, `DELETE /watches/{sku}` | Done (#101, PR #112) |
| `/alerts` | `GET /watches?user_id=` | Done (#101, PR #112) |
| Weekly digest | `GET /products?sort=recent` | Done (PR #107) |
| Restock alerts | `GET /watches/notifications`, `POST /watches/notifications/ack` | #138 |

## What's NOT in scope (yet)

- **AI recommendations** (`/recommend`) — Phase 6, requires ChromaDB + Claude
- **In-store availability** — would require scraping store-specific pages, not in sitemap data
- **Auth** — 20 friends, private bot, not needed yet

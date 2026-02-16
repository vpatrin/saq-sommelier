# Telegram Bot

## Why a bot?

SAQ.com already lets you browse, search, and filter wines. The bot's value is **proactive intelligence** — things SAQ doesn't do:

- Alert you when a watched wine's price drops or comes back in stock
- Push a weekly digest of new arrivals and price changes to a group chat
- Discover wines randomly or by filters without opening a browser
- Eventually: natural language recommendations via Claude (Phase 6)

Target audience: ~20 friends in a private group chat.

## Commands

| Command | Description | Example |
|---|---|---|
| `/search <query>` | Search wines by name | `/search mouton cadet` |
| `/new` | Recently added or updated wines | `/new` → filter by type/price |
| `/random` | Random wine suggestion | `/random` → filter by type/price |
| `/watch <sku>` | Get alerts for price drops and restocks | `/watch 10327701` |
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
- Price drops on popular categories
- Restocks of previously delisted wines

No command needed — it just shows up. Powered by the same data the scraper already collects.

## Availability model

Delisted products (removed from SAQ sitemap) are always excluded from the API. Online availability is an optional filter:

- `/search` — shows all products including out-of-stock, so users can find wines and set up alerts
- `/new`, `/random` — only available wines (`?available=true`), no point suggesting something you can't buy

`/watch` alerts on three events:

- **Online restock** — `availability` flips from `False` to `True` (back in stock)
- **Relist** — product reappears in the SAQ sitemap after being delisted
- **Price drop** — price decreased since last scrape (requires price history)

## Architecture

The bot is a separate service (`bot/`) that calls the FastAPI backend over HTTP. It does NOT access the database directly.

```
Telegram API → Bot service → FastAPI backend → PostgreSQL
```

No auth needed — the bot is the only API consumer for now. If/when the React dashboard is added, we'll revisit auth.

## API dependencies

Endpoints the bot needs from the backend:

| Bot feature | API endpoint | Status |
|---|---|---|
| `/search` | `GET /products?q=&category=&price_max=` | Exists |
| `/new` | `GET /products?sort=recent` | Missing — needs sort param |
| `/random` | `GET /products/random` | Missing — new endpoint |
| Filter buttons | `GET /products/facets` | Missing — #55 |
| `/watch` | `POST /watches`, `DELETE /watches/{sku}` | Missing — new resource |
| `/alerts` | `GET /watches` | Missing — new resource |
| Price drop alerts | Price history data | Missing — #57 |
| Weekly digest | Recent changes query | Missing — needs sort param |

## What's NOT in scope (yet)

- **AI recommendations** (`/recommend`) — Phase 6, requires ChromaDB + Claude
- **In-store availability** — would require scraping store-specific pages, not in sitemap data
- **Auth** — 20 friends, private bot, not needed yet

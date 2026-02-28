# Store Availability — Spec

Phase 5b. Cross-reference: [ROADMAP.md](../ROADMAP.md) for the full product phase sequence.

---

## What This Phase Delivers

- SAQ store directory in the database (401 stores)
- Per-user preferred store list (`/mystores` bot command, GPS-based)
- Per-product store stock levels for watched SKUs, checked daily
- Proactive alerts when a watched product restocks or destocks at a user's preferred stores

Out of scope: browsing or filtering products by store. SAQ.com already does this natively. Our value-add is the **proactive alert** — not replicating SAQ's catalog browser.

---

## API Reference

SAQ runs Magento 2 with Fastly CDN. Three data sources, each with different strengths:

| Source | What it gives us | Limitations |
|---|---|---|
| GraphQL | Online availability, price, magento_id (batch) | No per-store quantities, no wine attributes |
| AJAX store locator | Per-store quantities (per product, paginated) | No batching across products, page size fixed at 10 |
| HTML scrape | Wine attributes (grape, region, alcohol, ...) | CDN-cached (availability/price can be stale) |

### GraphQL (`POST /graphql`)

Unauthenticated Magento 2 GraphQL. No API key, no special headers.

**Request:**

```graphql
POST https://www.saq.com/graphql
Content-Type: application/json

{ products(filter: { sku: { in: ["15483332", "880500"] } }) {
    items { id sku stock_status }
}}
```

**Available fields on products:**

| Field | Type | Notes |
|---|---|---|
| `id` | Int | Magento internal ID — **required for AJAX store endpoint** |
| `sku` | String | SAQ product code |
| `name` | String | Product name |
| `stock_status` | Enum | `IN_STOCK` / `OUT_OF_STOCK` — **online purchase only**, stores can have stock independently |
| `price_range` | Object | `{minimum_price: {regular_price: {value, currency}, discount: {amount_off, percent_off}}}` |
| `rating_summary` | Float | Out of 100 (e.g. `80`) |
| `review_count` | Int | Number of reviews |
| `image` | Object | `{url, label}` — CDN image URL |
| `categories` | Array | Category names (Vin rouge, Pastilles de goût, etc.) |
| `only_x_left_in_stock` | Float | **Useless** — `null` when in stock, `0` when out. Mirrors `stock_status` |
| `description` | Object | **Empty** — SAQ doesn't populate this in Magento |
| `custom_attributesV2` | Object | **Broken** — returns Internal Server Error on SAQ's installation |

**Available filters (query-level):**

| Filter | Type | Notes |
|---|---|---|
| `sku: {in: [...]}` | Batch lookup | **Our primary use** — up to 20 per call |
| `store_availability_list: {eq: "23066"}` | Catalog filter | "Products at this store" — returns products, no qty. Not useful for per-product alerts |
| `cepage`, `region_origine`, `pays_origine`, `appellation` | Facet filters | Wine attributes as **filter inputs** only, not output fields |
| `price`, `pourcentage_alcool_par_volume` | Range filters | Numeric ranges |
| `name`, `nom_producteur` | Text match | Name/producer search |

**Key finding — `stock_status` is online only:**

Verified with SKU 880500 (Domaine Berthaut-Gerbet Fixin): GraphQL returns `OUT_OF_STOCK` but AJAX shows 20 stores with bottles (1-20 qty each). `stock_status` reflects whether the product is purchasable on saq.com, not whether physical stores carry it.

**Batching:** 20 SKUs per call is safe (tested). 50 watched SKUs = 3 calls.

**Introspection:** Schema is fully introspectable (`__type`, `__schema` queries). Discovered `store_availability_list` filter and all `ProductAttributeFilterInput` fields via introspection.

### AJAX store locator (`GET /fr/store/locator/ajaxlist`)

Paginated JSON endpoint. Requires `X-Requested-With: XMLHttpRequest` header.

**Parameters:**

| Param | Required | Default | Purpose |
|---|---|---|---|
| `context` | No | (none) | Set `"product"` for per-product stock. Without it: all 401 stores, no `qty` field |
| `id` | No | (none) | **Magento ID** (from GraphQL `id` field), not SKU. Only meaningful with `context=product` |
| `loaded` | No | `0` | Pagination offset. Increment by 10 (page size is hardcoded server-side, cannot be overridden) |
| `latitude` / `longitude` | No | (none) | Sort by proximity — **targeted fetch key** (see below) |
| `fastly_geolocate` | No | (none) | CDN auto-detect IP for proximity sort. **Not used** — irrelevant from VPS |

Tested and rejected: `limit`, `pageSize`, `count`, `radius`, `store_id`, `identifier`, `postal_code`, `zip` — all ignored by the server. Page size is fixed at 10. No single-store filtering exists.

**Targeted store fetch (optimization):** Pass a store's own lat/lng coordinates — that store appears first in results. One request per (product × store) instead of paginating through all ~112 stores. With 3 preferred stores: 3 requests vs ~11 pages per product.

**Store directory mode** (no `context`/`id`):

```text
GET /fr/store/locator/ajaxlist?loaded=0
→ 401 stores, 41 pages. No qty field.
```

**Per-product mode** (`context=product&id={magento_id}`):

```text
GET /fr/store/locator/ajaxlist?context=product&id=301436&loaded=0
→ Only stores carrying the product, with qty per store.
```

```json
{
  "total": 20,
  "is_last_page": false,
  "list": [{
    "identifier": "23066",
    "name": "Beaubien - St-André",
    "city": "Montréal",
    "qty": 1
  }]
}
```

Store count per product varies widely: niche wine ~20 stores (2 pages), popular wine 300+ stores (30+ pages).

Store types in production (from full 401-store fetch): SAQ (273), SAQ Sélection (91), SAQ Express (23), SAQ Dépôt (10), SAQ Restauration (3), Vin en vrac (1).

### Nearest store (shortcut)

```text
GET /fr/store/pointofsale/ajaxgetclosest/?latitude={lat}&longitude={lng}
X-Requested-With: XMLHttpRequest
```

Returns the **single nearest store** only. Not suitable for multi-store picker — use the full directory with lat/lng sort instead.

---

## Architecture Decisions

### Store primary key: `saq_store_id`

The API returns two IDs per store: `entity_id` (Magento internal, opaque integer) and `identifier` (SAQ store ID, e.g. `"23009"`). We use `identifier` as our PK. It appears in store URLs and is stable across API versions.

### Per-user store preferences: separate table

`UserStorePreference` maps `user_id → saq_store_id`. Users can have multiple preferred stores. The existing `Watch` table is **not modified** — no nullable store FK.

Rationale: mixing "what product I want" (Watch) with "where I want it" (UserStorePreference) into one table would require one row per (sku, store), making `/alerts` confusing. Keeping them separate means: one watch = one product; preferred stores are a user-level setting applied at alert time.

- No preferences → online-only alerts (current behavior, fully backward compatible)
- With preferences → alerts fire for online AND per-store stock changes

### Magento ID resolution: GraphQL batch, not HTML scraping

Originally planned to extract `magento_id` from `data-product-id` HTML during product scrape (#148). **Superseded.** The confirmed-unauthenticated GraphQL endpoint resolves SKUs to Magento IDs on demand — no stored column, no parser change, no migration. Issue #148 eliminated.

### Store availability storage: JSONB per product

One call to the availability endpoint returns **all stores** for a product. Store all results atomically. Filter by user preference at **alert time** via JOIN — not during fetch.

- **Normalized rows:** one row per `(sku, saq_store_id)` → ~5,600 rows for 50 SKUs × 112 stores avg. Simple to query individually.
- **JSONB (chosen):** `store_qty = {"23009": 44, "23132": 12}` on one row per product. Matches our access pattern exactly — we always read/write all stores for a product together.

### Two separate scraping timers

- **Weekly:** catalog attribute sync (name, region, grape, price, image, ...) + delist/relist detection. Does **not** emit StockEvents — availability data from HTML is CDN-cached and unreliable.
- **Daily (`--check-watches`):** online + store availability for **all watched SKUs** — GraphQL `stock_status` for online, AJAX for per-store quantities. AJAX runs for **all** SKUs regardless of `stock_status` (stores can have stock when online is OUT_OF_STOCK).

### `StockEvent` extension for store events

Extend with a nullable `saq_store_id`:

```python
saq_store_id = Column(String, ForeignKey("stores.saq_store_id"), nullable=True)
# NULL = online event (existing), non-NULL = store-level event
```

The bot's notification consumer already polls `StockEvent` — it just needs to check `saq_store_id` to render "online" vs "at Store X". One table, one consumer, one polling loop.

---

## Data Models

### `Store` (done — #128)

```python
class Store(Base):
    __tablename__ = "stores"
    saq_store_id       = Column(String, primary_key=True)
    name               = Column(String, nullable=False)
    store_type         = Column(String, nullable=True)
    address            = Column(String, nullable=True)
    city               = Column(String, nullable=False, index=True)
    postcode           = Column(String, nullable=True)
    telephone          = Column(String, nullable=True)
    latitude           = Column(Float, nullable=True)
    longitude          = Column(Float, nullable=True)
    temporarily_closed = Column(Boolean, nullable=False, default=False)
    created_at         = Column(DateTime(timezone=True), nullable=False)
```

Fields skipped: `entity_id`, `address2` (null for 59%), `opening_hours` (change daily), `region`/`country_id` (always Quebec/CA).

### `UserStorePreference` (new issue)

```python
class UserStorePreference(Base):
    __tablename__ = "user_store_preferences"
    user_id      = Column(String, primary_key=True)
    saq_store_id = Column(String, ForeignKey("stores.saq_store_id"), primary_key=True)
    created_at   = Column(DateTime(timezone=True), nullable=False)
```

### `ProductAvailability` (issue #149)

```python
class ProductAvailability(Base):
    __tablename__ = "product_availability"
    sku              = Column(String, ForeignKey("products.sku"), primary_key=True)
    online_available = Column(Boolean, nullable=True)     # GraphQL stock_status
    store_qty        = Column(JSONB, nullable=False, default=dict)
    # {"23009": 44, "23132": 12, ...}
    checked_at       = Column(DateTime(timezone=True), nullable=False)
```

---

## Implementation Sequence

### ✅ Issue #128 — Store directory

`Store` model, migration, `scraper/src/stores.py`, auto-bootstrap in `__main__.py`. Done.

---

### New Issue — UserStorePreference + `/mystores`

**Backend:** `GET /stores/nearby?lat=&lng=&limit=5`, `GET/POST/DELETE /users/{user_id}/stores`.

**Bot UX:**

```text
User: /mystores
Bot:  Nearest SAQ stores — tap to add:
      [Du Parc - Fairmount Ouest  1.2km]
      [Marché Atwater  2.1km]
      [Done ✓]
User: <taps stores, then Done>
Bot:  Saved. Your /watch alerts will now include these stores.
```

Post-`/watch` nudge if no stores set: *"Use /mystores to get in-store restock alerts."*

---

### ~~Issue #148 — Extract `magento_id`~~ — Eliminated

Superseded by GraphQL batch lookup. No stored column, no parser change.

---

### Issue #149 — Per-product availability checker (`--check-watches`)

**`scraper/src/availability.py`:**

```python
async def resolve_graphql_products(client, skus) -> dict[str, GraphQLProduct]: ...
async def fetch_store_availability(client, magento_id) -> dict[str, int]: ...
async def run_availability_check(client) -> int: ...
```

**Checker loop:**

```python
# 1. ALL watched SKUs (no store pref filter)
watched_skus = SELECT DISTINCT sku FROM watches

# 2. Batch-resolve via GraphQL (50 SKUs = 3 calls) → magento_id + stock_status
graphql_products = await resolve_graphql_products(client, watched_skus)

# 3. For each SKU:
for sku, gql in graphql_products.items():
    old_online, old_qty = await get_product_availability(sku)
    new_online = gql.stock_status == "IN_STOCK"

    # 3a. Online diff — emit StockEvent(saq_store_id=NULL) on transition
    if old_online is not None and old_online != new_online:
        await emit_stock_event(sku, available=new_online)

    # 3b. Store diff — ALWAYS fetch, regardless of stock_status
    #      (stores can have stock when online is OUT_OF_STOCK)
    new_qty = await fetch_store_availability(client, gql.magento_id)
    # ... diff old_qty vs new_qty, emit store StockEvents ...
    await upsert_product_availability(sku, online_available=new_online, store_qty=new_qty)
```

**Alert routing (bot notification consumer):**

```python
# Online events (saq_store_id IS NULL) → notify all watchers
# Store events (saq_store_id IS NOT NULL) → route via UserStorePreference JOIN
```

**Scale (with targeted fetch):** ~50 SKUs × GraphQL batch (~3 calls) + per SKU × target stores AJAX (1 request per store). With 3 preferred stores: 50 × 3 = 150 requests vs 50 × ~11 pages = 550.

**Notification format:**

```text
🍷 Viu Manent Malbec Reserva (750ml)
📦 Back in stock at Du Parc - Fairmount Ouest — 44 bottles
🔗 saq.com/fr/15483332
```

---

### ~~Issue #150 — Filter by store availability~~ — Out of scope

SAQ.com already does this. Our value-add is the proactive alert.

---

## Dependency Graph

```text
#128  Store directory            ──────────────────────────────┐
                                                                │
New   UserStorePreference        ── /mystores bot + /nearby ───┤
      model + API endpoints                                     │
                                                                ▼
                              GraphQL batch lookup ──── #149 Availability checker
                              (no #148 needed)                       + bot alerts
```

#128 and the UserStorePreference issue are independent — build in parallel. #149 needs both first.

## Operational Notes

- Store bootstrap: runs automatically on first scraper run (empty stores table). Re-run by clearing the table.
- Availability check (`--check-watches`): daily systemd timer, independent of weekly product scrape. Exits immediately if no watched SKUs exist.
- If GraphQL is down → checker logs and aborts gracefully; no partial writes.
- `product_availability` only contains rows for watched SKUs — not the full catalog.
- AJAX store check runs for ALL watched SKUs — `OUT_OF_STOCK` online does not imply empty stores (verified with real data).
- Weekly scrape does **not** emit StockEvents — CDN-cached HTML availability is unreliable. Only `--check-watches` emits events.
- See [CATALOG_AVAILABILITY.md](CATALOG_AVAILABILITY.md) for planned Phase 6 extension to full-catalog daily checks (needed for RAG).

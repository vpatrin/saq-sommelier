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

Common: `X-Requested-With: XMLHttpRequest` header required on all AJAX endpoints. Pagination: 10 per page, increment `loaded` by 10 until `is_last_page: true`.

### Store directory

```text
GET /fr/store/locator/ajaxlist?loaded={offset}&fastly_geolocate=1
```

401 stores, 41 pages. No `qty` field — pure directory.

```json
{
  "total": 401,
  "is_last_page": false,
  "list": [{
    "identifier": "23009",
    "name": "Du Parc - Fairmount Ouest",
    "address1": "5610, avenue du Parc",
    "city": "Montréal",
    "postcode": "H2V 4H9",
    "telephone": "514-274-0498",
    "latitude": "45.52071",
    "longitude": "-73.598804",
    "temporarily_closed": false,
    "additional_attributes": { "type": { "label": "SAQ" } }
  }]
}
```

Store types in production (confirmed from full 401-store fetch): SAQ (273), SAQ Sélection (91), SAQ Express (23), SAQ Dépôt (10), SAQ Restauration (3), Vin en vrac (1). Express/Dépôt stores have significantly different inventory levels — `store_type` is kept.

### Per-product store availability

```text
GET /fr/store/locator/ajaxlist/context/product/id/{magento_id}?loaded={offset}&fastly_geolocate=1
```

Same paginated shape, scoped to stores carrying the product. Adds `qty` per store. **No store filter param exists** — always returns all stores carrying the product. `lat/lng` params only affect sort order, not filtering. No auth required.

```json
{
  "total": 108,
  "is_last_page": false,
  "list": [{
    "identifier": "23009",
    "name": "Du Parc - Fairmount Ouest",
    "city": "Montréal",
    "qty": 45
  }]
}
```

### Magento GraphQL — confirmed unauthenticated

```graphql
POST /graphql
Content-Type: application/json

{ products(filter: { sku: { in: ["15483332", "14099363"] } }) {
    items { id sku name stock_status }
}}
```

Resolves SAQ SKU → Magento internal `id` in batch (tested: 3 SKUs → 3 IDs in one call). No API key, no headers required. **This eliminates the need to scrape product HTML for `magento_id`** — a major simplification vs the original plan.

```python
# 50 watched SKUs → 3 GraphQL calls (batch of 20) → ~1 second
POST /graphql { products(filter: { sku: { in: [...] } }) { items { id sku } } }
```

### Nearest store (shortcut)

```text
GET /fr/store/pointofsale/ajaxgetclosest/?latitude={lat}&longitude={lng}
X-Requested-With: XMLHttpRequest
```

Returns the **single nearest store** only. Not suitable for multi-store picker — use the full directory with lat/lng sort instead. Useful as a "quick pick nearest" shortcut.

### Online quantity (product page HTML)

The product page at `/fr/{sku}` contains an online stock count:

```python
re.search(r'(\d+)\s+available online', html).group(1)
```

Extractable during the existing product scrape — zero extra requests. Low-value for alerts (boolean IN_STOCK/OUT_OF_STOCK is sufficient). **Skipped for now.**

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

- **Weekly:** full product scrape (existing) — keeps catalog fresh, detects online restocks/destocks
- **Daily:** store availability check for **watched SKUs only** — ~18 min, delivers store alerts within 24h

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

### `ProductStoreAvailability` (issue #149)

```python
class ProductStoreAvailability(Base):
    __tablename__ = "product_store_availability"
    sku        = Column(String, ForeignKey("products.sku"), primary_key=True)
    store_qty  = Column(JSONB, nullable=False, default=dict)
    # {"23009": 44, "23132": 12, ...}
    checked_at = Column(DateTime(timezone=True), nullable=False)
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

### Issue #149 — Per-product store availability checker

**`scraper/src/availability.py`:**

```python
async def resolve_magento_ids(client, skus) -> dict[str, int]: ...
async def fetch_store_availability(client, magento_id) -> dict[str, int]: ...
async def run_availability_check(skus) -> None: ...
```

**Checker loop:**

```python
# 1. Watched SKUs with at least one user who has store preferences
watched_skus = SELECT DISTINCT w.sku FROM watches w
               WHERE EXISTS (SELECT 1 FROM user_store_preferences WHERE user_id = w.user_id)

# 2. Batch-resolve magento_ids (50 SKUs = 3 GraphQL calls)
magento_ids = await resolve_magento_ids(client, watched_skus)

# 3. For each SKU: fetch → diff → emit
for sku, magento_id in magento_ids.items():
    new_map = await fetch_store_availability(client, magento_id)
    old_map = (await get_product_store_availability(sku)).store_qty or {}
    restocked = {sid for sid in new_map if old_map.get(sid, 0) == 0 and new_map[sid] > 0}
    destocked  = {sid for sid in old_map if old_map[sid] > 0 and new_map.get(sid, 0) == 0}
    await upsert_product_store_availability(sku, new_map)
    for saq_store_id in restocked:
        await emit_store_stock_event(sku, saq_store_id, available=True)
```

**Alert routing (bot notification consumer):**

```python
# For each pending StockEvent with saq_store_id set:
notified_users = SELECT usp.user_id FROM user_store_preferences usp
                 WHERE usp.saq_store_id = event.saq_store_id
                 AND EXISTS (SELECT 1 FROM watches w WHERE w.user_id = usp.user_id AND w.sku = event.sku)
```

**Scale:** ~50 SKUs × 11 pages avg × 2s ≈ 18 min worst case.

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
- Availability check: daily systemd timer, independent of weekly product scrape. Exits immediately if no watched SKUs have users with store preferences.
- If GraphQL is down → checker logs and skips all SKUs gracefully; no partial writes.
- `product_store_availability` only contains rows for watched SKUs — not the full catalog.

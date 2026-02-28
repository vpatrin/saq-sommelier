# Catalog Availability for RAG — Spec

Phase 6 prerequisite. Cross-reference: [ROADMAP.md](../ROADMAP.md) Phase 6, [STORE_AVAILABILITY.md](STORE_AVAILABILITY.md) for current watch-based system.

---

## Problem

RAG recommendations need to know which products are available. Without availability data, Claude would recommend wines that have been out of stock for months.

The current architecture has two availability sources, neither sufficient for RAG:

- **`Product.availability`** — written by the weekly HTML scrape. Unreliable: CDN caching serves stale pages, and bulk `<lastmod>` edits trigger re-scrapes that find no real changes. Good enough for metadata (name, region, grape don't go stale), wrong tool for volatile availability data.
- **`ProductAvailability`** — written by the daily `--check-watches` job. Authoritative, but only covers watched SKUs (~tens of products). RAG needs the full catalog (~12k).

## Solution

Daily GraphQL batch for the full catalog. The SAQ Magento 2 GraphQL endpoint returns `stock_status` (enum: `IN_STOCK` / `OUT_OF_STOCK`) — a reliable, non-CDN-cached online availability flag. Querying all 12k SKUs costs ~600 calls (batches of 20) at ~2.5s rate limit = **~25 minutes**.

This replaces the weekly scrape as the source of truth for availability and price, while the weekly scrape continues to own wine-specific attributes that GraphQL doesn't expose.

---

## Architecture Change

### Current (watch-based, Phase 5b)

```
Weekly scrape (all 12k)        → Product metadata + availability (HTML, unreliable)
Daily --check-watches          → ProductAvailability for watched SKUs (GraphQL + AJAX)
```

### Future (this spec)

```
Weekly scrape (new products only)  → Wine attributes from HTML (grape, region, alcohol, ...)
Daily batch (all 12k)              → stock_status, price, magento_id from GraphQL
Daily batch (watched only)         → store_qty from AJAX (uses cached magento_id)
```

### What changes

| Concern | Before | After |
|---|---|---|
| Online availability source | Weekly HTML parse (CDN-cached) | Daily GraphQL `stock_status` |
| Price source | Weekly HTML parse | Daily GraphQL `price_range` |
| Magento ID | Resolved per-run, not stored | Cached on `Product.magento_id` |
| Store quantities | `ProductAvailability.store_qty` (JSONB) | `Product.store_qty` (JSONB) |
| Weekly scrape scope | All 12k product pages | Sitemap diff → HTML for new SKUs only |
| `ProductAvailability` table | Exists | **Dropped** — everything on `Product` |

### Product model changes

```python
# New columns
magento_id       = Column(Integer, nullable=True, comment="Magento internal ID (from GraphQL)")
store_qty        = Column(JSONB, nullable=True, comment='Store stock: {"23009": 44, ...}')
store_checked_at = Column(DateTime(timezone=True), nullable=True, comment="Last store availability check")

# Existing column, writer changes
availability     # writer: weekly HTML → daily GraphQL stock_status
price            # writer: weekly HTML → daily GraphQL price_range
```

`store_qty` and `store_checked_at` are NULL for the ~12k unwatched products. Only populated for watched SKUs with store preferences — same scope as today, just on the Product row instead of a separate table.

---

## Daily Batch Flow

```
1. Load all product SKUs from DB

2. GraphQL batch (all SKUs, batches of 20, ~600 calls)
   → For each product: stock_status, price, magento_id
   → Compare stock_status vs Product.availability
   → Emit StockEvent(saq_store_id=NULL) on transitions
   → Bulk update Product.availability, Product.price, Product.magento_id

3. Load watched SKUs with store preferences
   → Read Product.magento_id (cached from step 2)
   → AJAX fetch per-store quantities (always — stores carry stock independently of online status)
   → Diff old store_qty vs new store_qty
   → Emit StockEvent(saq_store_id=X) on transitions
   → Update Product.store_qty, Product.store_checked_at

4. Housekeeping: purge old stock events
```

Step 2 replaces the current `resolve_graphql_products()` call in `--check-watches` — no separate GraphQL resolution needed for watched SKUs.

### Performance estimate

| Step | Scope | API calls | Time |
|---|---|---|---|
| GraphQL batch | 12k SKUs / 20 per batch | ~600 | ~25 min |
| AJAX store fetch | ~50 watched SKUs × ~11 pages avg | ~550 | ~23 min |
| **Total** | | ~1,150 | **~48 min** |

Acceptable for a daily job on a VPS. Runs at 2am, nobody notices.

---

## Weekly Scrape Changes

The weekly scrape becomes a **catalog attribute sync**, not an availability tracker:

1. Fetch sitemap XML (same as today)
2. Sitemap diff: detect new SKUs and delisted SKUs
3. **New SKUs only**: fetch HTML, parse wine attributes (grape, region, alcohol, appellation, etc.)
4. Mark delisted products (`delisted_at`)
5. Relist products that reappear in sitemap

No more re-scraping 12k HTML pages weekly. Most weeks, only a few dozen new products appear.

### Why HTML is still needed

GraphQL doesn't expose wine-specific attributes:

| GraphQL has | HTML only (wine attributes) |
|---|---|
| `name`, `sku`, `stock_status` | **region**, **grape**, **appellation** |
| `price_range`, `description` | **alcohol**, **sugar**, **color** |
| `image`, `rating_summary` | **producer**, **classification** |
| `categories`, `review_count` | `saq_code`, `barcode`, `size` |

These attributes are static (a wine's grape and region never change) so scraping once per product is sufficient.

---

## GraphQL Reference

Confirmed unauthenticated, no API key required.

```graphql
POST https://www.saq.com/graphql
Content-Type: application/json

{
  products(filter: { sku: { in: ["14556190", "15483332"] } }) {
    items {
      id              # Magento internal ID (needed for AJAX store endpoint)
      sku
      name
      stock_status    # IN_STOCK | OUT_OF_STOCK
      price_range { minimum_price { regular_price { value currency } } }
    }
  }
}
```

`stock_status` enum (`ProductStockStatus`): `IN_STOCK`, `OUT_OF_STOCK`. Verified against real SKUs — returns accurate online availability, not CDN-cached.

The AJAX store locator (`/fr/store/locator/ajaxlist?context=product&id={magento_id}`) requires the Magento internal `id`, not the SKU. This is why `magento_id` must be resolved via GraphQL first.

---

## RAG Integration

With daily `stock_status` on every product, RAG can:

- Filter recommendations to `WHERE availability = true AND delisted_at IS NULL`
- Include store availability for users with store preferences: "Available at Du Parc (44 bottles)"
- Exclude wines that have been out of stock for extended periods

---

## Migration Path

This spec builds on top of the Phase 5b watch-based system, not alongside it:

1. **Phase 5b (current)**: `ProductAvailability` table, `--check-watches` with GraphQL + AJAX for watched SKUs only. Weekly scrape handles full catalog including availability.
2. **Phase 6 (this spec)**: Daily GraphQL batch for all 12k. `ProductAvailability` dropped, columns merged into `Product`. Weekly scrape scoped to new products only.

Phase 5b ships first. This spec is implemented when RAG is built (Phase 6), because that's when full-catalog availability becomes necessary.

---

## Open Questions

- **`custom_attributesV2`**: GraphQL field exists but returns Internal Server Error on SAQ's installation. If SAQ fixes this, it could expose wine attributes (grape, region) via GraphQL — potentially eliminating HTML scraping entirely. Monitor periodically.
- **Orphaned `store_qty`**: When all watches on a SKU are removed, `store_qty` stays on the Product row. Add cleanup to the daily batch (NULL out `store_qty` for unwatched SKUs). Low priority.
- **Delist notifications**: Currently `delisted_at` is set silently. Should emit a StockEvent so watchers are notified when SAQ removes a product entirely. Separate issue.

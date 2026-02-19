# SAQ Store & Availability — API Reference

## AJAX Endpoints

**Common:** `X-Requested-With: XMLHttpRequest` header required. Pagination: 10 per page, increment `loaded` by 10 until `is_last_page: true`.

### 1. Store Directory (no product context)

```text
GET /en/store/locator/ajaxlist?loaded={offset}&fastly_geolocate=1&_={ts}
```

401 stores, 41 pages. No `qty` field — pure directory.

```json
{
  "total": 401,
  "is_last_page": false,
  "list": [{
    "identifier": "23009",
    "name": "Du Parc - Fairmount Ouest",
    "address": ["5261, avenue du Parc"],
    "city": "Montréal",
    "postcode": "H2V4G9",
    "telephone": "514 277-8118",
    "latitude": "45.52071",
    "longitude": "-73.598804",
    "temporarily_closed": false,
    "opening_hours": [],
    "special_hours": []
  }]
}
```

**Use case:** Issue #128 — one-shot scrape, run once per deployment. Populate `stores` table.

### 2. Per-Product Store Availability

```text
GET /en/store/locator/ajaxlist/context/product/id/{magento_id}?loaded={offset}&fastly_geolocate=1
```

Same shape, but includes `qty` per store. Only returns stores carrying the product.

```json
{
  "total": 108,
  "is_last_page": false,
  "list": [{
    "identifier": "23009",
    "name": "Du Parc - Fairmount Ouest",
    "city": "Montréal",
    "qty": 45,
    "distance": "1,8 km"
  }]
}
```

Optional params: `latitude`/`longitude` for distance sorting.

**Use case:** `/watch` alerts — check stock for watched products at known stores.

### 3. Online Quantity (product page HTML)

The product page at `/en/{sku}` contains an online stock count in the HTML:

```text
"X available online"
```

```python
re.search(r'(\d+)\s+available online', html).group(1)
```

Extractable during the existing product scrape — zero extra requests.

## SAQ Product Listing Filters

SAQ's product listing pages support URL query params (all combinable):

| Filter | Param | Value |
| --- | --- | --- |
| New arrivals | `nouveaute_marketing` | `New Arrival` |
| New products | `nouveaute_marketing` | `New Product` |
| Online only | `availability_front` | `Online` |
| In-store only | `availability_front` | `In store` |
| Specific store | `store_availability_list[]` | store identifier (e.g. `23009`) |
| Category | path segment | `/products/wine`, `/products/spirits`, etc. |
| Page | `p` | page number |

**Caveat:** These pages are JS-rendered (Adobe GraphQL via `catalog-service.adobe.io`). Scraping them requires Playwright/Selenium — raw `requests` won't see the product grid.

**Decision: skip Playwright.** We already scrape all products from the sitemap, so `created_at` gives us "new this week" without a browser. Store availability comes from the AJAX endpoint. Playwright adds ~400MB to the Docker image and more RAM pressure on a 4GB VPS — not worth it for 20 users.

## SAQ Code → Magento ID

The availability endpoint uses Magento's internal entity ID, **not** the SAQ product code from the URL.

| SAQ code (in URL) | Magento ID (for API) |
| --- | --- |
| `15483332` | `409896` |

The Magento ID is on the product page price box:

```html
<div data-role="priceBox" data-product-id="409896">
```

Extract during the existing product scrape — zero extra requests:

```python
re.search(r'data-product-id="(\d+)"', html).group(1)
```

## How Features Map to Data Sources

### `/new` — Weekly New Arrivals

| Scope | Data source | Needs Playwright? |
| --- | --- | --- |
| Online | `products WHERE created_at >= 7 days ago` | No |
| In a specific store | Availability AJAX for recent products → filter by store | No |

### `/watch` — SKU Availability Alerts

| Scope | Data source | Method |
| --- | --- | --- |
| Online | Product page HTML | Parse `"X available online"` text |
| All stores | Availability AJAX (paginated) | Aggregate `qty` across all stores |
| Selected stores | Availability AJAX → filter by `identifier` | Check `qty` for each watched store |
| One store | Availability AJAX → find by `identifier` | Single store `qty` check |

## Engineering Plan

### Flow

```text
1. Store directory (one-shot) → stores table (401 rows)
2. Product scrape (existing) → now also extracts magento_id + online_qty
3. Availability check (per watched SKU):
     SELECT DISTINCT sku FROM watches
     → get magento_id from products table
     → paginate /context/product/id/{magento_id} until is_last_page
     → UPSERT into store_product_availability (sku, store_id, qty)
     → DIFF old vs new → emit alerts
```

### Scale

```text
~50 watched SKUs × ~3 pages avg (is_last_page early stop) × 2s rate limit
= ~300s ≈ 5 minutes
```

### Implementation Sequence

1. **#128 — Store directory** — `Store` model, one-shot `--stores` scrape (directory endpoint)
2. **Extract `magento_id` + `online_qty`** — add to `ProductData` + `Product`, update parser
3. **Availability checker** — `scraper/src/availability.py`, `store_product_availability` table, diff logic
4. **Bot alerts** — notify users whose watches triggered

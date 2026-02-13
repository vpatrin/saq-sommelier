# SAQ Sitemap & Product Page Findings

## Sitemap Structure

- Entry point: `https://www.saq.com/media/sitemaps/fr/sitemap_product.xml`
- This is a **sitemap index** pointing to 2 sub-sitemaps:
  - `sitemap_product_001.xml` — ~26k URLs
  - `sitemap_product_002.xml` — ~12k URLs
  - **~38k total products**
- Sub-sitemap files are large (~17MB each) — need streaming/chunked parsing
- Both sub-sitemaps have a `lastmod` at the index level

## Product URL Format

- Clean pattern: `https://www.saq.com/fr/{saq_code}`
- `saq_code` is numeric (e.g. `10327701`)
- Each entry includes:
  - `loc` — product URL
  - `lastmod` — last update timestamp (per product)
  - `changefreq` — always `daily`
  - `priority` — always `1.0`
  - `image:image` — (optional) product photo URL + title

## Product Page: Two Data Sources

### 1. JSON-LD (`<script type="application/ld+json">`)

Two Product blocks per page (same data, slightly different schemas). Only need to parse one. Fields:

| Field | Example |
|-------|---------|
| name | Kim Crawford Sauvignon Blanc Marlborough |
| sku | 10327701 |
| description | Free-text product description |
| image | Product photo URL |
| category | Vin blanc |
| countryOfOrigin | Nouvelle-Zélande |
| gtin12 | Barcode |
| color | Blanc |
| size | 750ml |
| offers.price | 22.50 |
| offers.priceCurrency | CAD |
| offers.availability | InStock / OutOfStock |
| manufacturer.name | Kim Crawford Wines Ltd. |
| aggregateRating | 4.6/5 (224 reviews) |

### 2. HTML Attributes (`<ul class="list-attributs">`)

Each attribute is a `<strong data-th="label">value</strong>`. Fields:

| Attribute | Example |
|-----------|---------|
| Pays | Nouvelle-Zélande |
| Région | South Island, Marlborough |
| Appellation d'origine | (varies) |
| Désignation réglementée | Vin de table (VDT) |
| Classification | (varies) |
| Cépage | Sauvignon blanc 100 % |
| Degré d'alcool | 13 % |
| Taux de sucre | 2,5 g/L |
| Couleur | Blanc |
| Format | 750 ml |
| Producteur | Kim Crawford Wines Ltd. |
| Agent promotionnel | (distributor) |
| Code SAQ | 10327701 |
| Code CUP | 00056049139096 |
| Produit du Québec | (if applicable) |

## What's Unique to Each Source

- **JSON-LD only**: price, availability, image, description, rating, barcode, category
- **HTML only**: region, grape, alcohol %, sugar, appellation, designation, classification

Both are needed. JSON-LD for core product info, HTML for wine-specific details.

## Data Quirks

- HTML entities in JSON-LD: `Fran&ccedil;ois` → needs `html.unescape()`
- `manufacturer` has entities (`&amp;`), `producer` from HTML does not
- `description` field is often empty — not reliable as a core field
- French decimals: `13,5 %` not `13.5 %`
- Volume formats: `750 ml`, `1 L`, `1.5 L`, `200 ml`
- Sugar: `2,5 g/L`
- Rating uses French comma: `4,6`
- Not all products have all fields — parser must handle missing attributes
- Some products are out of stock with minimal data (placeholder image, fewer attributes)

## Availability

- **Online**: from JSON-LD (`InStock` / `OutOfStock`) — simple boolean
- **In-store**: loaded via JavaScript/AJAX — not available from a simple HTTP fetch
- In-store would require reverse-engineering SAQ's internal API or a headless browser

## Schema Implications

- One flat table covers all product types (wine, spirits, beer)
- Wine-specific fields (grape, region, appellation, sugar) are nullable
- Spirits/beer simply have fewer fields populated
- Category field distinguishes product types

## Scraper Optimization (for later)

- `lastmod` per product in sitemap → only re-scrape products updated since last run
- `lastmod` per sub-sitemap in index → skip entire sub-sitemap if unchanged
- First scrape must hit everything; subsequent runs can be incremental

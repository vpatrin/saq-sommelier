import pytest
from core.config.test_utils import configure_test_db_env

configure_test_db_env()


@pytest.fixture
def sitemap_index_xml() -> str:
    """Minimal sitemap index XML with 2 sub-sitemap entries."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap>"
        "<loc>https://www.saq.com/media/sitemaps/fr/sitemap_product_001.xml</loc>"
        "<lastmod>2026-02-10</lastmod>"
        "</sitemap>"
        "<sitemap>"
        "<loc>https://www.saq.com/media/sitemaps/fr/sitemap_product_002.xml</loc>"
        "<lastmod>2026-02-09</lastmod>"
        "</sitemap>"
        "</sitemapindex>"
    )


@pytest.fixture
def sub_sitemap_xml() -> str:
    """Minimal sub-sitemap XML with 3 product URL entries."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url>"
        "<loc>https://www.saq.com/fr/10327701</loc>"
        "<lastmod>2026-02-01</lastmod>"
        "</url>"
        "<url>"
        "<loc>https://www.saq.com/fr/12345678</loc>"
        "<lastmod>2026-01-15</lastmod>"
        "</url>"
        "<url>"
        "<loc>https://www.saq.com/fr/99999999</loc>"
        "</url>"
        "</urlset>"
    )


@pytest.fixture
def product_page_html() -> str:
    """Product page HTML matching real SAQ structure (two JSON-LD blocks)."""
    return """<html><head>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Ch&acirc;teau Example Bordeaux",
  "sku": "10327701",
  "description": "A fine red wine",
  "category": "Vin rouge",
  "image": "https://www.saq.com/media/image.png?width=600&quality=80",
  "offers": {
    "price": 22.50,
    "priceCurrency": "CAD",
    "availability": "http://schema.org/InStock"
  }
}
</script>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Ch&acirc;teau Example Bordeaux",
  "sku": "10327701",
  "gtin12": "00012345678901",
  "category": "Vin rouge",
  "aggregateRating": {
    "ratingValue": "4,5",
    "reviewCount": "100"
  }
}
</script>
</head><body>
<ul class="list-attributs">
  <li><strong data-th="Pays">France</strong></li>
  <li><strong data-th="Couleur">Rouge</strong></li>
  <li><strong data-th="Format">750 ml</strong></li>
  <li><strong data-th="Région">Bordeaux</strong></li>
  <li><strong data-th="Appellation d'origine">Bordeaux AOC</strong></li>
  <li><strong data-th="Cépage">Merlot 60 %, Cabernet sauvignon 40 %</strong></li>
  <li><strong data-th="Degré d'alcool">13,5 %</strong></li>
  <li><strong data-th="Taux de sucre">2,5 g/L</strong></li>
  <li><strong data-th="Producteur">Château Example</strong></li>
  <li><strong data-th="Code SAQ">10327701</strong></li>
  <li><strong data-th="Code CUP">00012345678901</strong></li>
</ul>
</body></html>"""


@pytest.fixture
def product_page_html_bytes(product_page_html: str) -> bytes:
    """Product page HTML as raw bytes (simulates response.content)."""
    return product_page_html.encode("utf-8")


@pytest.fixture
def minimal_product_html() -> str:
    """Product page with minimal data (out of stock, few fields)."""
    return """<html><head>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Minimal Wine",
  "sku": "99999999",
  "offers": {
    "availability": "http://schema.org/OutOfStock"
  }
}
</script>
</head><body></body></html>"""

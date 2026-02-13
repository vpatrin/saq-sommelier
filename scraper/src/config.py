"""Scraper configuration — all tunable values in one place."""

SITEMAP_INDEX_URL = "https://www.saq.com/media/sitemaps/fr/sitemap_product.xml"
USER_AGENT = "SAQSommelier/0.1.0 (personal project; https://github.com/vpatrin/saq-sommelier)"
REQUEST_DELAY = 2.0  # seconds between requests (polite scraping)
HTTP_TIMEOUT = 30  # seconds

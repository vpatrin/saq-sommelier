"""SAQ product catalog scraper — fetch sitemap, parse products, print results."""

import dataclasses
import json
import time

import httpx

from .config import HTTP_TIMEOUT, REQUEST_DELAY, USER_AGENT
from .parser import parse_product
from .sitemap import fetch_sitemap_index, fetch_sub_sitemap


def main(max_products: int = 5) -> None:
    """Fetch sitemap, scrape a few products, print parsed data.

    Args:
        max_products: Number of products to scrape (default 5, for testing).
    """
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT) as client:
        print("Fetching sitemap index...")
        sub_sitemap_urls = fetch_sitemap_index(client)
        print(f"Found {len(sub_sitemap_urls)} sub-sitemaps")

        time.sleep(REQUEST_DELAY)

        print("\nFetching first sub-sitemap...")
        entries = fetch_sub_sitemap(client, sub_sitemap_urls[0])
        print(f"Found {len(entries)} product URLs")

        print(f"\nScraping first {max_products} products...\n")
        for entry in entries[:max_products]:
            time.sleep(REQUEST_DELAY)
            print(f"Fetching {entry.url}...")
            response = client.get(entry.url)
            response.raise_for_status()

            product = parse_product(response.text)
            print(
                json.dumps(dataclasses.asdict(product), indent=2, ensure_ascii=False, default=str)
            )
            print()


if __name__ == "__main__":
    main()

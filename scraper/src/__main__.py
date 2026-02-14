"""SAQ product catalog scraper — fetch sitemap, parse products, write to database."""

import asyncio

import httpx

from .config import settings
from .db import upsert_product
from .parser import parse_product
from .sitemap import fetch_sitemap_index, fetch_sub_sitemap


async def main(max_products: int = 5) -> None:
    """Fetch sitemap, scrape products, write to database.

    Args:
        max_products: Number of products to scrape (default 5, for testing).
                     Set to None or a very large number to scrape all products.
    """

    # async with keeps a connection pool open (reuses TCP connections)
    # User-Agent identifies us as a bot (ethical scraping)
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.USER_AGENT}, timeout=settings.REQUEST_TIMEOUT
    ) as client:
        print("Fetching sitemap index...")
        sub_sitemap_urls = await fetch_sitemap_index(client)
        print(f"Found {len(sub_sitemap_urls)} sub-sitemaps\n")

        await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

        # We only fetch first sub sitemap for now
        print("Fetching first sub-sitemap...")
        entries = await fetch_sub_sitemap(client, sub_sitemap_urls[0])
        print(f"Found {len(entries)} product URLs\n")

        # If max_products is None, scrape all
        products_to_scrape = entries[:max_products] if max_products else entries
        print(f"Scraping {len(products_to_scrape)} products...\n")

        #! Main scrape loop
        for i, entry in enumerate(products_to_scrape, 1):
            # Ethical rate limiter
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

            print(f"[{i}/{len(products_to_scrape)}] Fetching {entry.url}...", end=" ")

            try:
                # Download HTML
                response = await client.get(entry.url)
                response.raise_for_status()

                # Parse HTML and create a ProductData instance
                product = parse_product(response.text, url=entry.url)

                # Saves to DB (upsert)
                await upsert_product(product)
                print(f"✓ Saved {product.sku or 'unknown'} - {product.name or 'no name'}")

            except httpx.HTTPError as e:
                print(f"✗ HTTP error: {e}")
            except Exception as e:
                print(f"✗ Error: {e}")

        print(f"\n✓ Done! Scraped {len(products_to_scrape)} products.")


if __name__ == "__main__":
    asyncio.run(main())

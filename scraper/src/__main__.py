import asyncio

import httpx
from core.logging import setup_logging
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .db import upsert_product
from .parser import parse_product
from .sitemap import fetch_sitemap_index, fetch_sub_sitemap

setup_logging(settings.SERVICE_NAME, level=settings.LOG_LEVEL)


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
        logger.info("Fetching sitemap index...")
        sub_sitemap_urls = await fetch_sitemap_index(client)
        logger.info("Found {} sub-sitemaps", len(sub_sitemap_urls))

        await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

        # We only fetch first sub sitemap for now
        logger.info("Fetching first sub-sitemap...")
        entries = await fetch_sub_sitemap(client, sub_sitemap_urls[0])
        logger.info("Found {} product URLs", len(entries))

        # If max_products is None, scrape all
        products_to_scrape = entries[:max_products] if max_products else entries
        logger.info("Scraping {} products...", len(products_to_scrape))

        # Main scrape loop
        for i, entry in enumerate(products_to_scrape, 1):
            # Ethical rate limiter
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

            try:
                # Download HTML
                logger.info("[{}/{}] Fetching {}...", i, len(products_to_scrape), entry.url)
                response = await client.get(entry.url)
                response.raise_for_status()

                # Parse HTML and create a ProductData instance
                product = parse_product(response.text, url=entry.url)

                # Saves to DB (upsert)
                await upsert_product(product)
                logger.success("Saved {} - {}", product.sku or "unknown", product.name or "no name")

            except httpx.HTTPError as e:
                logger.error("HTTP error for {}: {}", entry.url, e)
            except SQLAlchemyError:
                logger.error("DB error for {}, skipping", entry.url)
            except Exception:
                logger.exception("Unexpected error for {}", entry.url)

        logger.success("Done! Scraped {} products", len(products_to_scrape))


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sys
import time
from datetime import date

import httpx
from core.logging import setup_logging
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .db import clear_delisted, get_delisted_skus, get_updated_dates, mark_delisted, upsert_product
from .parser import parse_product
from .sitemap import SitemapEntry, fetch_sitemap_index, fetch_sub_sitemap

setup_logging(settings.SERVICE_NAME, level=settings.LOG_LEVEL)


def _exit_code(saved: int, errors: int) -> int:
    """Determine process exit code from scrape results."""
    if errors == 0:
        return 0  # Clean run
    if saved > 0:
        return 1  # Partial failure
    return 2  # Total failure


def _needs_scrape(entry: SitemapEntry, updated_dates: dict[str, date]) -> bool:
    """Check if a sitemap entry needs to be scraped.

    Returns True (scrape) when:
    - No lastmod in sitemap (can't determine staleness)
    - Product not in DB yet (new product)
    - Sitemap lastmod is newer than DB updated_at
    """
    if not entry.lastmod:
        return True
    if entry.sku not in updated_dates:
        return True
    return date.fromisoformat(entry.lastmod) > updated_dates[entry.sku]


async def main() -> int:
    """Fetch sitemap, scrape products, write to database. Returns exit code."""
    # monotonic is immune to system clock changes
    start = time.monotonic()

    # async with keeps a connection pool open (reuses TCP connections)
    # User-Agent identifies us as a bot (ethical scraping)
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.USER_AGENT}, timeout=settings.REQUEST_TIMEOUT
    ) as client:
        logger.info("Fetching sitemap index...")
        sub_sitemap_urls = await fetch_sitemap_index(client)
        logger.info("Found {} sub-sitemaps", len(sub_sitemap_urls))

        # Fetch all sub-sitemaps, collecting entries into one list
        entries = []
        for j, sub_url in enumerate(sub_sitemap_urls, 1):
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)
            logger.info("[{}/{}] Fetching sub-sitemap...", j, len(sub_sitemap_urls))
            entries.extend(await fetch_sub_sitemap(client, sub_url))

        logger.info(
            "Found {} total product URLs across {} sub-sitemaps",
            len(entries),
            len(sub_sitemap_urls),
        )

        limit = settings.SCRAPE_LIMIT
        products_to_scrape = entries[:limit] if limit else entries

        # Loads {sku: last_updated_date} from DB, then O(1) dict lookup per entry
        updated_dates = await get_updated_dates()

        # Incremental scraping: skip products unchanged since last scrape
        total_before = len(products_to_scrape)
        products_to_scrape = [e for e in products_to_scrape if _needs_scrape(e, updated_dates)]
        skipped = total_before - len(products_to_scrape)

        logger.info(
            "Incremental filter: {} to scrape, {} skipped (unchanged)",
            len(products_to_scrape),
            skipped,
        )

        # Main scrape loop
        saved = 0
        inserted = 0
        updated = 0
        errors = 0
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
                saved += 1
                if entry.sku in updated_dates:
                    updated += 1
                else:
                    inserted += 1
                logger.success("Saved {} - {}", product.sku or "unknown", product.name or "no name")

            except httpx.HTTPError as e:
                errors += 1
                logger.error("HTTP error for {}: {}", entry.url, e)
            except SQLAlchemyError:
                errors += 1
                logger.error("DB error for {}, skipping", entry.url)
            except Exception:
                errors += 1
                logger.exception("Unexpected error for {}", entry.url)

    # Delist detection: compare sitemap SKUs vs DB SKUs
    # Best-effort — if it fails, next run catches up
    delisted = 0
    relisted = 0
    sitemap_skus = {e.sku for e in entries}
    db_skus = set(updated_dates.keys())

    try:
        to_delist = db_skus - sitemap_skus
        delisted = await mark_delisted(to_delist)
        if delisted:
            logger.info("Marked {} products as delisted", delisted)

        currently_delisted = await get_delisted_skus()
        to_relist = currently_delisted & sitemap_skus
        relisted = await clear_delisted(to_relist)
        if relisted:
            logger.info("Relisted {} products (back in sitemap)", relisted)
    except SQLAlchemyError:
        logger.error("Delist detection failed, skipping")

    # Run summary
    elapsed = time.monotonic() - start
    hours, remainder = divmod(int(elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)

    logger.info(
        "Scraper run complete:\n"
        "  Duration: {}h {}m {}s\n"
        "  Sitemap URLs: {}\n"
        "  Fetched: {}\n"
        "  Inserted: {}\n"
        "  Updated: {}\n"
        "  Failed: {}\n"
        "  Skipped (up-to-date): {}\n"
        "  Delisted: {}\n"
        "  Relisted: {}",
        hours,
        minutes,
        seconds,
        len(entries),
        saved,
        inserted,
        updated,
        errors,
        skipped,
        delisted,
        relisted,
    )

    return _exit_code(saved, errors)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

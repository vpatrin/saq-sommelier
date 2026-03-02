import asyncio
import sys
import time
import urllib.error
from datetime import date, datetime
from http import HTTPStatus

import httpx
from core.logging import setup_logging
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from .availability import run_availability_check
from .config import settings
from .constants import EXIT_FATAL, EXIT_OK, EXIT_PARTIAL
from .db import (
    clear_delisted,
    delete_old_stock_events,
    emit_stock_event,
    get_availability_map,
    get_delisted_skus,
    get_updated_dates,
    mark_delisted,
    stores_populated,
    upsert_product,
    upsert_stores,
)
from .products import parse_product
from .robots import is_allowed, load_robots
from .sitemap import SitemapEntry, fetch_sitemap_index, fetch_sub_sitemap
from .stores import fetch_stores

setup_logging(settings.SERVICE_NAME, level=settings.LOG_LEVEL)


def _exit_code(saved: int, errors: int) -> int:
    """Determine process exit code from scrape results."""
    if errors == 0:
        return EXIT_OK
    if saved > 0:
        return EXIT_PARTIAL
    return EXIT_FATAL


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
    return datetime.fromisoformat(entry.lastmod).date() > updated_dates[entry.sku]


async def main() -> int:
    """Fetch sitemap, scrape products, write to database. Returns exit code."""
    # monotonic is immune to system clock changes
    start = time.monotonic()

    # async with keeps a connection pool open (reuses TCP connections)
    # User-Agent identifies us as a bot (ethical scraping)
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.USER_AGENT}, timeout=settings.REQUEST_TIMEOUT
    ) as client:
        # Bootstrap store directory on first run — stores are physical locations,
        # rarely change. Re-populate by clearing the stores table and re-running.
        if not await stores_populated():
            logger.info("Stores table empty — bootstrapping store directory...")
            try:
                stores = await fetch_stores(client)
                await upsert_stores(stores)
                logger.info("Store bootstrap complete: {} stores loaded", len(stores))
            except (httpx.HTTPError, SQLAlchemyError, ValueError, KeyError) as exc:
                logger.warning("Store bootstrap failed — continuing without store data: {}", exc)

        logger.info("Fetching sitemap index...")
        sub_sitemap_urls = await fetch_sitemap_index(client)
        logger.info("Found {} sub-sitemaps", len(sub_sitemap_urls))

        # Fetch all sub-sitemaps, collecting entries into one list
        entries = []
        for j, sub_url in enumerate(sub_sitemap_urls, 1):
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)
            logger.info("[{}/{}] Fetching sub-sitemap...", j, len(sub_sitemap_urls))
            entries.extend(await fetch_sub_sitemap(client, sub_url))

        # Load robots.txt rules (one sync HTTP call, fail-fast for compliance)
        try:
            rp = load_robots(settings.ROBOTS_URL)
        except urllib.error.URLError as exc:
            logger.opt(exception=exc).error("Cannot fetch robots.txt — aborting to ensure compliance")
            return EXIT_FATAL

        # Filter URLs disallowed by robots.txt
        before_robots = len(entries)
        entries = [e for e in entries if is_allowed(rp, e.url, settings.USER_AGENT)]
        skipped_robots = before_robots - len(entries)

        # Filter non-product URLs (recipes, accessories have slug SKUs, not numeric)
        total_sitemap = len(entries)
        entries = [e for e in entries if e.sku.isdigit()]
        skipped_non_products = total_sitemap - len(entries)

        logger.info(
            "Found {} product URLs across {} sub-sitemaps"
            " ({} blocked by robots.txt, {} non-products skipped)",
            len(entries),
            len(sub_sitemap_urls),
            skipped_robots,
            skipped_non_products,
        )

        limit = settings.SCRAPE_LIMIT
        products_to_scrape = entries[:limit] if limit else entries

        # Loads {sku: last_updated_date} from DB, then O(1) dict lookup per entry
        try:
            updated_dates = await get_updated_dates()
            availability_map = await get_availability_map()
        except SQLAlchemyError as exc:
            logger.opt(exception=exc).error("DB error loading product data — aborting")
            return EXIT_FATAL

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
        restocked = 0
        destocked = 0
        not_found = 0
        errors = 0
        for i, entry in enumerate(products_to_scrape, 1):
            # Ethical rate limiter
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

            try:
                # Download HTML
                logger.info("[{}/{}] Fetching {} ...", i, len(products_to_scrape), entry.url)
                response = await client.get(entry.url)
                response.raise_for_status()

                # Parse HTML and create a ProductData instance
                product = parse_product(response.content, url=entry.url)

                # Saves to DB (upsert)
                await upsert_product(product)
                saved += 1
                if entry.sku in updated_dates:
                    updated += 1
                else:
                    inserted += 1

                # Detect availability transitions
                old_avail = availability_map.get(entry.sku)
                if old_avail is False and product.availability:
                    await emit_stock_event(entry.sku, available=True)
                    restocked += 1
                    logger.info("Restock detected for SKU {}", entry.sku)
                elif old_avail is True and not product.availability:
                    await emit_stock_event(entry.sku, available=False)
                    destocked += 1
                    logger.info("Destock detected for SKU {}", entry.sku)

                logger.success("Saved {} - {}", product.sku or "unknown", product.name or "no name")

            except httpx.HTTPStatusError as e:
                if e.response.status_code == HTTPStatus.NOT_FOUND:
                    not_found += 1
                    logger.warning("Not found (stale sitemap entry): {}", entry.url)
                else:
                    errors += 1
                    logger.error("HTTP error for {}: {}", entry.url, e)
            except httpx.HTTPError as e:
                errors += 1
                logger.error("HTTP error for {}: {}", entry.url, e)
            except SQLAlchemyError as exc:
                errors += 1
                logger.error("DB error for {}: {}", entry.url, exc)
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
    except SQLAlchemyError as exc:
        logger.opt(exception=exc).warning("Delist detection failed, skipping")

    # Housekeeping: purge old stock events
    await delete_old_stock_events(days=settings.STOCK_EVENT_RETENTION_DAYS)

    # Run summary
    elapsed = time.monotonic() - start
    hours, remainder = divmod(int(elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)

    logger.info(
        "Scraper run complete:\n"
        "  Duration: {}h {}m {}s\n"
        "  Sitemap URLs: {}\n"
        "  Skipped (robots.txt): {}\n"
        "  Fetched: {}\n"
        "  Inserted: {}\n"
        "  Updated: {}\n"
        "  Restocked: {}\n"
        "  Destocked: {}\n"
        "  Not found: {}\n"
        "  Failed: {}\n"
        "  Skipped (up-to-date): {}\n"
        "  Delisted: {}\n"
        "  Relisted: {}",
        hours,
        minutes,
        seconds,
        len(entries),
        skipped_robots,
        saved,
        inserted,
        updated,
        restocked,
        destocked,
        not_found,
        errors,
        skipped,
        delisted,
        relisted,
    )

    return _exit_code(saved, errors)


async def check_watches() -> int:
    """Check online + store availability for watched SKUs. Returns exit code."""
    start = time.monotonic()

    async with httpx.AsyncClient(
        headers={"User-Agent": settings.USER_AGENT}, timeout=settings.REQUEST_TIMEOUT
    ) as client:
        try:
            events = await run_availability_check(client)
        except Exception:
            logger.exception("Watch availability check failed")
            return EXIT_FATAL

    # Housekeeping: purge old stock events (same as weekly scrape)
    await delete_old_stock_events(days=settings.STOCK_EVENT_RETENTION_DAYS)

    elapsed = time.monotonic() - start
    minutes, seconds = divmod(int(elapsed), 60)
    logger.info(
        "Watch availability check done in {}m {}s — {} events emitted", minutes, seconds, events
    )
    return EXIT_OK


if __name__ == "__main__":
    # Entry point: python -m src [--check-watches]
    if "--check-watches" in sys.argv:
        sys.exit(asyncio.run(check_watches()))
    else:
        sys.exit(asyncio.run(main()))

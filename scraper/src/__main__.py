import asyncio
import sys
import time
import urllib.error
from dataclasses import dataclass
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
    get_delisted_skus,
    get_updated_dates,
    mark_delisted,
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


async def _load_and_filter_entries(
    client: httpx.AsyncClient,
) -> list[SitemapEntry] | None:
    """Fetch sitemaps, apply robots.txt and product filters.

    Returns filtered entries, or None if robots.txt fetch fails (caller should abort).
    """
    logger.info("Fetching sitemap index...")
    sub_sitemap_urls = await fetch_sitemap_index(client)
    logger.info("Found {} sub-sitemaps", len(sub_sitemap_urls))

    entries: list[SitemapEntry] = []
    for j, sub_url in enumerate(sub_sitemap_urls, 1):
        await asyncio.sleep(settings.RATE_LIMIT_SECONDS)
        logger.info("[{}/{}] Fetching sub-sitemap...", j, len(sub_sitemap_urls))
        entries.extend(await fetch_sub_sitemap(client, sub_url))

    # Load robots.txt rules (one sync HTTP call, fail-fast for compliance)
    try:
        rp = load_robots(settings.ROBOTS_URL)
    except urllib.error.URLError as exc:
        logger.opt(exception=exc).error("Cannot fetch robots.txt — aborting to ensure compliance")
        return None

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

    return entries


@dataclass
class _ScrapeStats:
    saved: int = 0
    inserted: int = 0
    updated: int = 0
    not_found: int = 0
    errors: int = 0


async def _scrape_products(
    client: httpx.AsyncClient,
    entries: list[SitemapEntry],
    updated_dates: dict[str, date],
) -> _ScrapeStats:
    """Download, parse, and upsert each product entry. Returns run stats."""
    stats = _ScrapeStats()

    for i, entry in enumerate(entries, 1):
        # Ethical rate limiter
        await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

        try:
            logger.info("[{}/{}] Fetching {} ...", i, len(entries), entry.url)
            response = await client.get(entry.url)
            response.raise_for_status()

            product = parse_product(response.content, url=entry.url)
            await upsert_product(product)
            stats.saved += 1
            if entry.sku in updated_dates:
                stats.updated += 1
            else:
                stats.inserted += 1

            logger.success("Saved {} - {}", product.sku or "unknown", product.name or "no name")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                stats.not_found += 1
                logger.warning("Not found (stale sitemap entry): {}", entry.url)
            else:
                stats.errors += 1
                logger.error("HTTP error for {}: {}", entry.url, e)
        except httpx.HTTPError as e:
            stats.errors += 1
            logger.error("HTTP error for {}: {}", entry.url, e)
        except SQLAlchemyError as exc:
            stats.errors += 1
            logger.error("DB error for {}: {}", entry.url, exc)
        except Exception:
            stats.errors += 1
            logger.exception("Unexpected error for {}", entry.url)

    return stats


async def _detect_delists(sitemap_skus: set[str], db_skus: set[str]) -> tuple[int, int]:
    """Compare sitemap vs DB SKUs and mark/clear delisted products.

    Returns (delisted, relisted). Best-effort — logs and returns (0, 0) on error.
    """
    # Delist detection: compare sitemap SKUs vs DB SKUs
    # Best-effort — if it fails, next run catches up
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

        return delisted, relisted
    except SQLAlchemyError as exc:
        logger.opt(exception=exc).warning("Delist detection failed, skipping")
        return 0, 0


async def main() -> int:
    """Fetch sitemap, scrape products, write to database. Returns exit code."""
    # monotonic is immune to system clock changes
    start = time.monotonic()

    # async with keeps a connection pool open (reuses TCP connections)
    # User-Agent identifies us as a bot (ethical scraping)
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.USER_AGENT}, timeout=settings.REQUEST_TIMEOUT
    ) as client:
        entries = await _load_and_filter_entries(client)
        if entries is None:
            return EXIT_FATAL

        # Loads {sku: last_updated_date} from DB, then O(1) dict lookup per entry
        try:
            updated_dates = await get_updated_dates()
        except SQLAlchemyError as exc:
            logger.opt(exception=exc).error("DB error loading product data — aborting")
            return EXIT_FATAL

        # Incremental scraping: skip products unchanged since last scrape
        limit = settings.SCRAPE_LIMIT
        products_to_scrape = entries[:limit] if limit else entries
        total_before = len(products_to_scrape)
        products_to_scrape = [e for e in products_to_scrape if _needs_scrape(e, updated_dates)]
        skipped = total_before - len(products_to_scrape)
        logger.info(
            "Incremental filter: {} to scrape, {} skipped (unchanged)",
            len(products_to_scrape),
            skipped,
        )

        stats = await _scrape_products(client, products_to_scrape, updated_dates)

    sitemap_skus = {e.sku for e in entries}
    db_skus = set(updated_dates.keys())
    delisted, relisted = await _detect_delists(sitemap_skus, db_skus)

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
        "  Fetched: {}\n"
        "  Inserted: {}\n"
        "  Updated: {}\n"
        "  Not found: {}\n"
        "  Failed: {}\n"
        "  Skipped (up-to-date): {}\n"
        "  Delisted: {}\n"
        "  Relisted: {}",
        hours,
        minutes,
        seconds,
        len(entries),
        stats.saved,
        stats.inserted,
        stats.updated,
        stats.not_found,
        stats.errors,
        skipped,
        delisted,
        relisted,
    )

    return _exit_code(stats.saved, stats.errors)


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


async def scrape_stores() -> int:
    """Fetch and upsert the full SAQ store directory. Returns exit code."""
    start = time.monotonic()

    async with httpx.AsyncClient(
        headers={"User-Agent": settings.USER_AGENT}, timeout=settings.REQUEST_TIMEOUT
    ) as client:
        try:
            stores = await fetch_stores(client)
            await upsert_stores(stores)
        except (httpx.HTTPError, SQLAlchemyError, ValueError, KeyError) as exc:
            logger.opt(exception=exc).error("Store scrape failed")
            return EXIT_FATAL

    elapsed = time.monotonic() - start
    minutes, seconds = divmod(int(elapsed), 60)
    logger.info(
        "Store scrape complete in {}m {}s — {} stores loaded", minutes, seconds, len(stores)
    )
    return EXIT_OK


if __name__ == "__main__":
    # Entry point: python -m src [--check-watches | --scrape-stores]
    if "--check-watches" in sys.argv:
        sys.exit(asyncio.run(check_watches()))
    elif "--scrape-stores" in sys.argv:
        sys.exit(asyncio.run(scrape_stores()))
    else:
        sys.exit(asyncio.run(main()))

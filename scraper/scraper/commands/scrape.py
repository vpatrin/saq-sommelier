import asyncio
import time
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus

import httpx
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..constants import EXIT_FATAL, EXIT_OK, EXIT_PARTIAL
from ..db import (
    ProductState,
    clear_delisted,
    delete_old_stock_events,
    emit_stock_event,
    get_delisted_skus,
    get_product_states,
    get_watched_skus,
    mark_delisted,
    upsert_product,
)
from ..products import compute_content_hash, parse_product
from ..robots import is_allowed, load_robots
from ..sitemap import SitemapEntry, fetch_sitemap_index, fetch_sub_sitemap


def _exit_code(saved: int, errors: int) -> int:
    """Determine process exit code from scrape results."""
    if errors == 0:
        return EXIT_OK
    if saved > 0:
        return EXIT_PARTIAL
    return EXIT_FATAL


def _needs_scrape(entry: SitemapEntry, product_states: dict[str, ProductState]) -> bool:
    """Check if a sitemap entry needs to be scraped.

    Returns True (scrape) when:
    - No lastmod in sitemap (can't determine staleness)
    - Product not in DB yet (new product)
    - Sitemap lastmod is newer than DB updated_at
    """
    if not entry.lastmod:
        return True
    if entry.sku not in product_states:
        return True
    return datetime.fromisoformat(entry.lastmod).date() > product_states[entry.sku].updated_date


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
    unchanged: int = 0
    not_found: int = 0
    errors: int = 0


async def _scrape_products(
    client: httpx.AsyncClient,
    entries: list[SitemapEntry],
    product_states: dict[str, ProductState],
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
            content_hash = compute_content_hash(product)

            # Skip DB write if content hasn't changed
            existing = product_states.get(entry.sku)
            if existing and existing.content_hash == content_hash:
                stats.unchanged += 1
                logger.debug("Unchanged {}", product.sku or "unknown")
                continue

            await upsert_product(product, content_hash)
            stats.saved += 1
            if entry.sku in product_states:
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

        if to_delist:
            watched = set(await get_watched_skus())
            for sku in to_delist & watched:
                await emit_stock_event(sku, available=False)
                logger.info("Emitted delist event for watched SKU {}", sku)

        currently_delisted = await get_delisted_skus()
        to_relist = currently_delisted & sitemap_skus
        relisted = await clear_delisted(to_relist)
        if relisted:
            logger.info("Relisted {} products (back in sitemap)", relisted)

        return delisted, relisted
    except SQLAlchemyError as exc:
        logger.opt(exception=exc).warning("Delist detection failed, skipping")
        return 0, 0


async def scrape_products() -> int:
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

        # Loads {sku: ProductState} from DB, then O(1) dict lookup per entry
        try:
            product_states = await get_product_states()
        except SQLAlchemyError as exc:
            logger.opt(exception=exc).error("DB error loading product data — aborting")
            return EXIT_FATAL

        # Incremental scraping: skip products unchanged since last scrape
        limit = settings.SCRAPE_LIMIT
        products_to_scrape = entries[:limit] if limit else entries
        total_before = len(products_to_scrape)
        products_to_scrape = [e for e in products_to_scrape if _needs_scrape(e, product_states)]
        skipped = total_before - len(products_to_scrape)
        logger.info(
            "Incremental filter: {} to scrape, {} skipped (unchanged lastmod)",
            len(products_to_scrape),
            skipped,
        )

        stats = await _scrape_products(client, products_to_scrape, product_states)

    sitemap_skus = {e.sku for e in entries}
    db_skus = set(product_states.keys())
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
        "  Unchanged (hash match): {}\n"
        "  Not found: {}\n"
        "  Failed: {}\n"
        "  Skipped (up-to-date lastmod): {}\n"
        "  Delisted: {}\n"
        "  Relisted: {}",
        hours,
        minutes,
        seconds,
        len(entries),
        stats.saved + stats.unchanged + stats.not_found + stats.errors,
        stats.inserted,
        stats.updated,
        stats.unchanged,
        stats.not_found,
        stats.errors,
        skipped,
        delisted,
        relisted,
    )

    return _exit_code(stats.saved, stats.errors)

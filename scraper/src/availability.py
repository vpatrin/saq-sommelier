import time
from dataclasses import dataclass, field

import httpx
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from .adobe import PaginationCapError, build_filters, search_products
from .config import settings
from .constants import EXIT_FATAL, EXIT_OK, EXIT_PARTIAL
from .db import (
    bulk_update_availability,
    delete_old_stock_events,
    emit_stock_event,
    get_montreal_store_ids,
    get_preferred_store_ids,
    get_watched_product_availability,
)


@dataclass
class _AvailabilityData:
    """Accumulated availability from Adobe queries, keyed by SKU."""

    online: dict[str, bool] = field(default_factory=dict)
    stores: dict[str, list[str]] = field(default_factory=dict)

    @property
    def skus(self) -> set[str]:
        return set(self.online) | set(self.stores)


async def _fetch_in_stock(client: httpx.AsyncClient, data: _AvailabilityData) -> int:
    """Query 1a: inStock=true — all online-purchasable products."""
    filters = build_filters(in_stock=True)
    count = 0
    async for product in search_products(client, filters):
        data.online[product.sku] = True
        store_ids = product.attributes.get("store_availability_list", [])
        if isinstance(store_ids, list):
            data.stores[product.sku] = store_ids
        count += 1
    logger.info("Query 1a (inStock=true): {} products", count)
    return count


async def _fetch_montreal_stores(
    client: httpx.AsyncClient,
    data: _AvailabilityData,
    store_ids: list[str],
) -> int:
    """Query 1b: Montreal in filter — En succursale products at Montreal stores."""
    filters = build_filters(store_ids=store_ids)
    count = 0
    new = 0
    async for product in search_products(client, filters):
        count += 1
        if product.sku in data.online:
            continue  # already seen in 1a, skip
        new += 1
        # Use Adobe's inStock value (often false for En succursale-only products)
        data.online[product.sku] = product.in_stock
        store_list = product.attributes.get("store_availability_list", [])
        if isinstance(store_list, list):
            data.stores[product.sku] = store_list
    logger.info(
        "Query 1b (Montreal stores): {} products ({} new, {} deduped)", count, new, count - new
    )
    return new


@dataclass
class _TransitionStats:
    online_restock: int = 0
    online_destock: int = 0
    store_restock: int = 0
    store_destock: int = 0
    errors: int = 0


async def _detect_transitions(data: _AvailabilityData) -> _TransitionStats:
    """Step 2: compare previous vs new availability for watched products, emit StockEvents."""
    stats = _TransitionStats()

    prev_avail = await get_watched_product_availability()
    if not prev_avail:
        logger.info("No watched products — skipping transition detection")
        return stats

    preferred = await get_preferred_store_ids()

    for sku, (prev_online, prev_stores) in prev_avail.items():
        new_online = data.online.get(sku)
        new_store_list = data.stores.get(sku, [])
        new_store_set = set(new_store_list)
        prev_store_set = set(prev_stores) if prev_stores else set()

        # Online transition
        if prev_online is not None and new_online is not None and prev_online != new_online:
            try:
                await emit_stock_event(sku, available=new_online)
                if new_online:
                    stats.online_restock += 1
                else:
                    stats.online_destock += 1
            except SQLAlchemyError:
                stats.errors += 1
        elif prev_online is True and new_online is None:
            # Was online, disappeared from Adobe results → destock
            try:
                await emit_stock_event(sku, available=False)
                stats.online_destock += 1
            except SQLAlchemyError:
                stats.errors += 1

        # Store transitions — only for user-preferred stores, and only if
        # the product appeared in Adobe results (absent SKUs keep stale data)
        if sku not in data.skus:
            continue
        user_stores = preferred.get(sku, set())
        for store_id in user_stores:
            was_available = store_id in prev_store_set
            now_available = store_id in new_store_set
            if was_available != now_available:
                try:
                    await emit_stock_event(sku, available=now_available, saq_store_id=store_id)
                    if now_available:
                        stats.store_restock += 1
                    else:
                        stats.store_destock += 1
                except SQLAlchemyError:
                    stats.errors += 1

    logger.info(
        "Transitions: online +{}/−{}, store +{}/−{}, errors {}",
        stats.online_restock,
        stats.online_destock,
        stats.store_restock,
        stats.store_destock,
        stats.errors,
    )
    return stats


async def availability_check() -> int:
    """Daily availability refresh from Adobe Live Search. Returns exit code."""
    start = time.monotonic()

    # Load Montreal store IDs from DB
    try:
        montreal_ids = await get_montreal_store_ids()
    except SQLAlchemyError as exc:
        logger.opt(exception=exc).error("Failed to load Montreal store IDs — aborting")
        return EXIT_FATAL
    if not montreal_ids:
        logger.error("No Montreal stores found in DB — run --scrape-stores first")
        return EXIT_FATAL
    logger.info("Loaded {} Montreal consumer stores", len(montreal_ids))

    data = _AvailabilityData()

    # Step 1: Adobe queries
    async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
        try:
            await _fetch_in_stock(client, data)
            await _fetch_montreal_stores(client, data, montreal_ids)
        except PaginationCapError as exc:
            logger.opt(exception=exc).error("Adobe pagination cap exceeded — aborting")
            return EXIT_FATAL
        except httpx.HTTPError as exc:
            logger.opt(exception=exc).error("Adobe API request failed — aborting")
            return EXIT_FATAL

    logger.info("Step 1 complete: {} unique products collected", len(data.skus))

    # Step 1 write: bulk-update availability columns
    updates = {sku: (data.online.get(sku, False), data.stores.get(sku, [])) for sku in data.skus}
    try:
        updated = await bulk_update_availability(updates)
        logger.info("Updated availability for {} products", updated)
    except SQLAlchemyError:
        return EXIT_FATAL

    # Step 2: watch transition detection
    transitions = await _detect_transitions(data)

    # Step 3: housekeeping
    await delete_old_stock_events(days=settings.STOCK_EVENT_RETENTION_DAYS)

    # Summary
    elapsed = time.monotonic() - start
    minutes, seconds = divmod(int(elapsed), 60)
    logger.info(
        "Availability check complete in {}m {}s:\n"
        "  Products updated: {}\n"
        "  Online restocks: {}\n"
        "  Online destocks: {}\n"
        "  Store restocks: {}\n"
        "  Store destocks: {}\n"
        "  Event errors: {}",
        minutes,
        seconds,
        updated,
        transitions.online_restock,
        transitions.online_destock,
        transitions.store_restock,
        transitions.store_destock,
        transitions.errors,
    )

    if transitions.errors > 0:
        return EXIT_PARTIAL
    return EXIT_OK

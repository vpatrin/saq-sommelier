import asyncio
import json
from dataclasses import dataclass

import httpx
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .db import (
    emit_stock_event,
    get_product_availability,
    get_watched_skus,
    upsert_product_availability,
)

_GRAPHQL_URL = "https://www.saq.com/graphql"
_STORE_AVAILABILITY_URL = "https://www.saq.com/fr/store/locator/ajaxlist"
_GRAPHQL_BATCH_SIZE = 20  # tested safe; TODO: test upper limit for Phase 6 (12k SKUs)
_MAX_PAGES = 50  # safety valve: 500 stores max (SAQ has ~400)


@dataclass
class GraphQLProduct:
    magento_id: int
    stock_status: str  # "IN_STOCK" or "OUT_OF_STOCK"


async def resolve_graphql_products(
    client: httpx.AsyncClient, skus: list[str]
) -> dict[str, GraphQLProduct]:
    """Batch-resolve SAQ SKUs → GraphQLProduct(Magento ID + stock_status) via GraphQL."""
    result: dict[str, GraphQLProduct] = {}

    for i in range(0, len(skus), _GRAPHQL_BATCH_SIZE):
        batch = skus[i : i + _GRAPHQL_BATCH_SIZE]
        sku_filter = json.dumps(batch)
        query = (
            "{ products(filter: { sku: { in: "
            + sku_filter
            + " } }) { items { id sku stock_status } }}"
        )

        try:
            response = await client.post(
                _GRAPHQL_URL,
                json={"query": query},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("data", {}).get("products", {}).get("items", []):
                result[item["sku"]] = GraphQLProduct(
                    magento_id=int(item["id"]),
                    stock_status=item.get("stock_status", "OUT_OF_STOCK"),
                )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.error("GraphQL batch failed (SKUs {}-{}): {}", i, i + len(batch), exc)

        if i + _GRAPHQL_BATCH_SIZE < len(skus):
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

    return result


async def fetch_store_availability(client: httpx.AsyncClient, magento_id: int) -> dict[str, int]:
    """Fetch all stores carrying a product → {store_id: qty}."""
    store_qty: dict[str, int] = {}
    offset = 0
    is_last_page = False
    page = 0
    SAQ_PAGE_SIZE = 10

    while not is_last_page and page < _MAX_PAGES:
        page += 1
        params = {
            "context": "product",
            "id": str(magento_id),
            "loaded": offset,
        }
        try:
            response = await client.get(
                _STORE_AVAILABILITY_URL,
                params=params,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error(
                "Store availability fetch failed (id={}, offset={}): {}", magento_id, offset, exc
            )
            break

        for store in data.get("list", []):
            store_id = store.get("identifier")
            qty = store.get("qty", 0)
            if store_id:
                store_qty[store_id] = int(qty)

        is_last_page = data.get("is_last_page", True)

        if not is_last_page:
            offset += SAQ_PAGE_SIZE  # SAQ page size is server-enforced, not configurable
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

    if page >= _MAX_PAGES:
        logger.warning(
            "Hit max page limit for magento_id={} (got {} stores)", magento_id, len(store_qty)
        )

    return store_qty


async def run_availability_check(client: httpx.AsyncClient) -> int:
    """Check online + store availability for all watched SKUs.

    Returns the number of stock events emitted.
    """
    skus = await get_watched_skus()
    if not skus:
        logger.info("No watched SKUs — skipping availability check")
        return 0

    logger.info("Checking availability for {} watched SKUs", len(skus))

    graphql_products = await resolve_graphql_products(client, skus)
    if not graphql_products:
        logger.warning("GraphQL resolved 0 products — aborting")
        return 0

    unresolved = set(skus) - set(graphql_products.keys())
    if unresolved:
        logger.warning("Could not resolve {} SKUs: {}", len(unresolved), unresolved)

    online_restocks = 0
    online_destocks = 0
    store_restocks = 0
    store_destocks = 0
    baselines = 0
    errors = 0
    total = len(graphql_products)

    for i, (sku, gql) in enumerate(graphql_products.items(), 1):
        logger.info("[{}/{}] {} ({})", i, total, sku, gql.stock_status)

        try:
            # What's currently in DB
            old_online, old_qty = await get_product_availability(sku)
            new_online = gql.stock_status == "IN_STOCK"
            is_first_check = old_online is None

            # Online availability diff
            if not is_first_check and old_online != new_online:
                await emit_stock_event(sku, available=new_online)
                if new_online:
                    online_restocks += 1
                else:
                    online_destocks += 1
                label = "RESTOCK" if new_online else "DESTOCK"
                logger.info("{} (online): {}", label, sku)

            # Store availability — ALWAYS check, regardless of online stock_status.
            # Stores can carry stock when online is OUT_OF_STOCK (verified with SKU 880500).
            new_qty = await fetch_store_availability(client, gql.magento_id)
            logger.info("  {} stores carrying stock", len(new_qty))

            # Store diff: only emit events if we have a baseline (not first check).
            # First check establishes the snapshot — no diff to compare.
            if is_first_check:
                baselines += 1
            else:
                all_stores = set(old_qty.keys()) | set(new_qty.keys())
                for store_id in all_stores:
                    old_val = old_qty.get(store_id, 0)
                    new_val = new_qty.get(store_id, 0)

                    if old_val == 0 and new_val > 0:
                        await emit_stock_event(sku, available=True, saq_store_id=store_id)
                        store_restocks += 1
                        logger.info("RESTOCK: {} at store {} ({} bottles)", sku, store_id, new_val)
                    elif old_val > 0 and new_val == 0:
                        await emit_stock_event(sku, available=False, saq_store_id=store_id)
                        store_destocks += 1
                        logger.info(
                            "DESTOCK: {} at store {} (was {} bottles)", sku, store_id, old_val
                        )

            await upsert_product_availability(sku, online_available=new_online, store_qty=new_qty)
        except SQLAlchemyError:
            errors += 1
            logger.error("DB error processing SKU {} — skipping", sku)

        await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

    events_emitted = online_restocks + online_destocks + store_restocks + store_destocks
    logger.info(
        "Availability check complete:\n"
        "  Watched SKUs: {}\n"
        "  Resolved: {}\n"
        "  Unresolved: {}\n"
        "  First-check baselines: {}\n"
        "  Online restocks: {}\n"
        "  Online destocks: {}\n"
        "  Store restocks: {}\n"
        "  Store destocks: {}\n"
        "  Total events: {}\n"
        "  Errors: {}",
        len(skus),
        total,
        len(skus) - total,
        baselines,
        online_restocks,
        online_destocks,
        store_restocks,
        store_destocks,
        events_emitted,
        errors,
    )
    return events_emitted

import ast
import time
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from .adobe import AdobeProduct, PaginationCapError, build_filters, fetch_facets, search_products
from .config import settings
from .constants import EXIT_FATAL, EXIT_OK
from .db import bulk_update_wine_attrs, get_all_skus

# Wine subcategory paths in SAQ's Adobe catalog
_WINE_SUBCATEGORIES = [
    "produits/vin/vin-rouge",
    "produits/vin/vin-blanc",
    "produits/vin/vin-rose",
    "produits/champagne-et-mousseux",
    "produits/porto-et-vin-fortifie",
    "produits/sake",
]

# Price range partitions for countries exceeding 10k products (France vin-rouge)
_PRICE_RANGES: list[tuple[float, float]] = [
    (0, 20),
    (20, 50),
    (50, 100),
    (100, 500),
    (500, 99999),
]

# Portrait attributes to collapse into tasting_profile JSONB
_PORTRAIT_ATTRS = {
    "portrait_acidite": "acidite",
    "portrait_arome": "arome",
    "portrait_bois": "bois",
    "portrait_bouche": "bouche",
    "portrait_corps": "corps",
    "portrait_sucre": "sucre",
    "portrait_potentiel_de_garde": "potentiel_garde",
}


def extract_wine_attrs(attrs: dict[str, str | list[str]]) -> dict[str, Any]:
    """Transform Adobe attributes into the 4 Product columns.

    Returns a dict with keys: taste_tag, vintage, tasting_profile, grape_blend.
    Empty strings from Adobe become None.
    """
    taste_tag = attrs.get("pastille_gout", "") or None
    vintage = attrs.get("millesime_produit", "") or None

    # Build tasting_profile from portrait_* attributes
    profile: dict[str, Any] = {}
    for adobe_key, col_key in _PORTRAIT_ATTRS.items():
        val = attrs.get(adobe_key, "")
        if val:
            profile[col_key] = val

    # Temperature range — two separate Adobe fields collapsed to a list
    temp_from = attrs.get("portrait_temp_service_de", "")
    temp_to = attrs.get("portrait_temp_service_a", "")
    if temp_from or temp_to:
        try:
            temp_service = [
                int(temp_from) if temp_from else None,
                int(temp_to) if temp_to else None,
            ]
            profile["temp_service"] = temp_service
        except (ValueError, TypeError):
            pass

    tasting_profile = profile if profile else None

    # Grape blend: cepage_text is a stringified JSON object like '{"MALB":"96","SYRA":"4"}'
    grape_blend = _parse_grape_blend(attrs.get("cepage_text", ""))

    return {
        "taste_tag": taste_tag,
        "vintage": vintage,
        "tasting_profile": tasting_profile,
        "grape_blend": grape_blend,
    }


def _parse_grape_blend(raw: str | list[str]) -> list[dict[str, str | int]] | None:
    """Parse Adobe cepage_text into structured blend list.

    Input: '{"MALB":"96","SYRA":"4"}' or empty string
    Output: [{"code": "MALB", "pct": 96}, {"code": "SYRA", "pct": 4}] or None
    """
    if not raw or isinstance(raw, list):
        return None
    try:
        # Adobe returns Python-style dicts with single quotes, not JSON
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(parsed, dict) or not parsed:
        return None
    blend = []
    for code, pct_str in parsed.items():
        try:
            blend.append({"code": code, "pct": int(pct_str)})
        except (ValueError, TypeError):
            blend.append({"code": code, "pct": 0})
    return blend


async def _collect_subcategory(
    client: httpx.AsyncClient,
    subcategory: str,
    collected: dict[str, dict[str, Any]],
) -> int:
    """Fetch all products for a wine subcategory, partitioning if needed.

    Returns count of products collected.
    """
    count = 0
    filters = build_filters(categories=subcategory)
    try:
        async for product in search_products(client, filters):
            _collect_product(product, collected)
            count += 1
        logger.info("{}: {} products (direct)", subcategory.split("/")[-1], count)
        return count
    except PaginationCapError as exc:
        logger.info(
            "{}: {} products — partitioning by country",
            subcategory.split("/")[-1],
            exc.total_count,
        )

    # Partition by country
    countries = await fetch_facets(client, filters, "pays_origine")
    logger.info("{}: {} countries from facets", subcategory.split("/")[-1], len(countries))

    sub = subcategory.split("/")[-1]
    for i, country in enumerate(countries, 1):
        logger.info("{} [{}/{}]: {}", sub, i, len(countries), country)
        country_filters = build_filters(categories=subcategory, country=country)
        try:
            async for product in search_products(client, country_filters):
                _collect_product(product, collected)
                count += 1
        except PaginationCapError:
            logger.info("{} × {} exceeds 10k — sub-partitioning by price", sub, country)
            for lo, hi in _PRICE_RANGES:
                logger.info("{} × {} × ${}-${}", sub, country, int(lo), int(hi))
                price_filters = build_filters(
                    categories=subcategory, country=country, price_range=(lo, hi)
                )
                async for product in search_products(client, price_filters):
                    _collect_product(product, collected)
                    count += 1

    logger.info("{}: {} products (partitioned)", subcategory.split("/")[-1], count)
    return count


def _collect_product(product: AdobeProduct, collected: dict[str, dict[str, Any]]) -> None:
    """Extract wine attrs from an AdobeProduct and add to collected dict."""
    wine_attrs = extract_wine_attrs(product.attributes)
    # Skip products with no enrichment data at all
    if any(v is not None for v in wine_attrs.values()):
        collected[product.sku] = wine_attrs


async def enrich_wines() -> int:
    """One-time Adobe attribute backfill for wine products. Returns exit code."""
    start = time.monotonic()

    # Load known SKUs — only update products already in our DB
    try:
        known_skus = await get_all_skus()
    except SQLAlchemyError as exc:
        logger.opt(exception=exc).error("Failed to load product SKUs — aborting")
        return EXIT_FATAL

    if not known_skus:
        logger.error("No products in DB — run the scraper first")
        return EXIT_FATAL

    logger.info("Loaded {} known SKUs from DB", len(known_skus))

    collected: dict[str, dict[str, Any]] = {}

    async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
        for subcategory in _WINE_SUBCATEGORIES:
            try:
                await _collect_subcategory(client, subcategory, collected)
            except PaginationCapError as exc:
                logger.opt(exception=exc).error(
                    "Pagination cap in price sub-partition for {} — aborting", subcategory
                )
                return EXIT_FATAL
            except httpx.HTTPError as exc:
                logger.opt(exception=exc).error("Adobe API request failed — aborting")
                return EXIT_FATAL

    logger.info("Collected {} wine products from Adobe", len(collected))

    # Filter to known SKUs only
    to_update = {sku: attrs for sku, attrs in collected.items() if sku in known_skus}
    skipped = len(collected) - len(to_update)
    if skipped:
        logger.info("{} Adobe products not in DB — skipped", skipped)

    if not to_update:
        logger.warning("No matching products to update")
        return EXIT_OK

    # Bulk write
    try:
        updated = await bulk_update_wine_attrs(to_update)
        logger.info("Updated wine attributes for {} products", updated)
    except SQLAlchemyError:
        return EXIT_FATAL

    elapsed = time.monotonic() - start
    minutes, seconds = divmod(int(elapsed), 60)
    logger.info(
        "Wine enrichment complete in {}m {}s:\n"
        "  Adobe products: {}\n"
        "  DB matches: {}\n"
        "  Skipped (not in DB): {}",
        minutes,
        seconds,
        len(collected),
        len(to_update),
        skipped,
    )

    return EXIT_OK

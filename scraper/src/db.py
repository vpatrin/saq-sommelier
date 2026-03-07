from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from core.db.base import create_session_factory
from core.db.models import (
    Product,
    StockEvent,
    Store,
    UserStorePreference,
    Watch,
)
from loguru import logger
from sqlalchemy import bindparam, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .products import ProductData
from .stores import StoreData

_SessionLocal = create_session_factory(settings.database_url, settings.database_echo)


async def get_all_skus() -> set[str]:
    """Return the set of all product SKUs in the DB."""
    async with _SessionLocal() as session:
        result = await session.execute(select(Product.sku))
        return {row[0] for row in result.all()}


async def get_updated_dates() -> dict[str, date]:
    """Fetch the last-updated date for every product in the DB."""
    async with _SessionLocal() as session:
        stmt = select(Product.sku, Product.updated_at)
        result = await session.execute(stmt)
        return {sku: updated_at.date() for sku, updated_at in result.all()}


async def get_delisted_skus() -> set[str]:
    """Get SKUs of products currently marked as delisted."""
    async with _SessionLocal() as session:
        stmt = select(Product.sku).where(Product.delisted_at.isnot(None))
        result = await session.execute(stmt)
        return {row[0] for row in result.all()}


async def mark_delisted(skus: set[str]) -> int:
    """Set delisted_at on given SKUs. Returns count updated."""
    if not skus:
        return 0
    async with _SessionLocal() as session:
        stmt = (
            update(Product)
            .where(Product.sku.in_(skus))
            .where(Product.delisted_at.is_(None))
            .values(delisted_at=datetime.now(UTC))
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def clear_delisted(skus: set[str]) -> int:
    """Clear delisted_at on given SKUs (relist). Returns count updated."""
    if not skus:
        return 0
    async with _SessionLocal() as session:
        stmt = (
            update(Product)
            .where(Product.sku.in_(skus))
            .where(Product.delisted_at.isnot(None))
            .values(delisted_at=None)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def emit_stock_event(sku: str, available: bool, *, saq_store_id: str | None = None) -> None:
    """Record an availability transition in the stock_events table.

    saq_store_id: NULL = online event, non-NULL = in-store event.
    """
    async with _SessionLocal() as session:
        values: dict[str, Any] = {"sku": sku, "available": available}
        if saq_store_id is not None:
            values["saq_store_id"] = saq_store_id
        stmt = pg_insert(StockEvent).values(**values)
        try:
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error("Failed to emit stock event for SKU {}", sku)
            raise


async def delete_old_stock_events(days: int) -> None:
    """Delete stock events older than the given number of days.

    Best-effort — swallows errors so a failed cleanup never crashes the scraper.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with _SessionLocal() as session:
        stmt = delete(StockEvent).where(StockEvent.detected_at < cutoff)
        try:
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount:
                logger.info("Purged {} stock events older than {} days", result.rowcount, days)
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).warning("Stock event cleanup failed, skipping")


async def upsert_product(product_data: ProductData) -> None:
    """Insert or update a product in the database.

    Uses PostgreSQL's INSERT ON CONFLICT DO UPDATE (upsert) to:
    - Insert new product if SKU doesn't exist
    - Update existing product if SKU already exists

    Args:
        product_data: Parsed product data from scraper

    Pattern:
        INSERT INTO products (sku, name, price, ...)
        VALUES (...)
        ON CONFLICT (sku) DO UPDATE
        SET name = EXCLUDED.name, price = EXCLUDED.price, updated_at = NOW()
    """
    async with _SessionLocal() as session:
        product_dict = asdict(product_data)
        now = datetime.now(UTC)
        product_dict["created_at"] = now
        product_dict["updated_at"] = now

        stmt = pg_insert(Product).values(product_dict)

        # On conflict (SKU already exists), update all fields except sku and created_at
        update_dict = {k: v for k, v in product_dict.items() if k not in ["sku", "created_at"]}
        update_dict["updated_at"] = now

        stmt = stmt.on_conflict_do_update(
            index_elements=list(Product.__table__.primary_key),
            set_=update_dict,  # Update these fields
        )

        try:
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error(
                "DB error upserting SKU {}", product_data.sku or "unknown"
            )
            raise


async def get_watched_skus() -> list[str]:
    """Get all distinct SKUs from the watches table."""
    async with _SessionLocal() as session:
        stmt = select(Watch.sku).distinct()
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


async def get_montreal_store_ids() -> list[str]:
    """Get consumer-facing Montreal store IDs (excludes SAQ Restauration)."""
    async with _SessionLocal() as session:
        stmt = (
            select(Store.saq_store_id)
            .where(Store.city == "Montréal")
            .where(Store.store_type != "SAQ Restauration")
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


_BULK_CHUNK_SIZE = 1000


async def bulk_update_availability(
    updates: dict[str, tuple[bool, list[str]]],
) -> int:
    """Batch-update online_availability and store_availability for multiple SKUs.

    Uses Core-level UPDATE with bindparam, chunked to avoid oversized statements.
    ORM update() doesn't support bindparam WHERE — Core Table bypasses that.

    Args:
        updates: {sku: (online_availability, store_ids_list)}

    Returns number of SKUs submitted.
    """
    if not updates:
        return 0
    all_params = [
        {"_sku": sku, "online": online, "stores": stores or None}  # [] → NULL
        for sku, (online, stores) in updates.items()
    ]
    table = Product.__table__
    stmt = (
        update(table)
        .where(table.c.sku == bindparam("_sku"))
        .values(online_availability=bindparam("online"), store_availability=bindparam("stores"))
    )
    async with _SessionLocal() as session:
        try:
            for i in range(0, len(all_params), _BULK_CHUNK_SIZE):
                chunk = all_params[i : i + _BULK_CHUNK_SIZE]
                await session.execute(stmt, chunk)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error(
                "Failed to bulk-update availability for {} SKUs", len(updates)
            )
            raise
    return len(updates)


async def bulk_update_wine_attrs(
    updates: dict[str, dict[str, str | list | dict | None]],
) -> int:
    """Batch-update wine attributes (taste_tag, vintage, tasting_profile, grape_blend).

    Args:
        updates: {sku: {taste_tag, vintage, tasting_profile, grape_blend}}

    Returns number of SKUs submitted.
    """
    if not updates:
        return 0
    all_params = [
        {
            "_sku": sku,
            "taste_tag": attrs.get("taste_tag"),
            "vintage": attrs.get("vintage"),
            "tasting_profile": attrs.get("tasting_profile"),
            "grape_blend": attrs.get("grape_blend"),
        }
        for sku, attrs in updates.items()
    ]
    table = Product.__table__
    stmt = (
        update(table)
        .where(table.c.sku == bindparam("_sku"))
        .values(
            taste_tag=bindparam("taste_tag"),
            vintage=bindparam("vintage"),
            tasting_profile=bindparam("tasting_profile"),
            grape_blend=bindparam("grape_blend"),
        )
    )
    async with _SessionLocal() as session:
        try:
            for i in range(0, len(all_params), _BULK_CHUNK_SIZE):
                chunk = all_params[i : i + _BULK_CHUNK_SIZE]
                await session.execute(stmt, chunk)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error(
                "Failed to bulk-update wine attributes for {} SKUs", len(updates)
            )
            raise
    return len(updates)


async def get_products_needing_embedding() -> list[dict]:
    """Fetch products where embedding_input_hash != last_embedded_hash (or NULL).

    Returns dicts with all fields needed to build embedding text + compute hash.
    """
    async with _SessionLocal() as session:
        stmt = select(
            Product.sku,
            Product.category,
            Product.taste_tag,
            Product.tasting_profile,
            Product.grape_blend,
            Product.grape,
            Product.producer,
            Product.region,
            Product.appellation,
            Product.designation,
            Product.classification,
            Product.country,
            Product.vintage,
            Product.description,
            Product.embedding_input_hash,
        ).where(
            (Product.embedding_input_hash != Product.last_embedded_hash)
            | (Product.last_embedded_hash.is_(None))
        )
        result = await session.execute(stmt)
        return [row._asdict() for row in result.all()]


async def bulk_update_embeddings(
    updates: list[dict],
) -> int:
    """Batch-update embedding vectors and last_embedded_hash.

    Args:
        updates: list of {sku, embedding, last_embedded_hash}
    """
    if not updates:
        return 0
    table = Product.__table__
    stmt = (
        update(table)
        .where(table.c.sku == bindparam("_sku"))
        .values(
            embedding=bindparam("_embedding"),
            last_embedded_hash=bindparam("_hash"),
        )
    )
    params = [
        {"_sku": u["sku"], "_embedding": u["embedding"], "_hash": u["last_embedded_hash"]}
        for u in updates
    ]
    async with _SessionLocal() as session:
        try:
            for i in range(0, len(params), _BULK_CHUNK_SIZE):
                chunk = params[i : i + _BULK_CHUNK_SIZE]
                await session.execute(stmt, chunk)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error(
                "Failed to bulk-update embeddings for {} SKUs", len(updates)
            )
            raise
    return len(updates)


async def get_watched_product_availability() -> dict[str, tuple[bool | None, list[str] | None]]:
    """Load current availability for all watched, non-delisted products.

    Returns {sku: (online_availability, store_availability)}.
    """
    async with _SessionLocal() as session:
        stmt = (
            select(Product.sku, Product.online_availability, Product.store_availability)
            .join(Watch, Product.sku == Watch.sku)
            .where(Product.delisted_at.is_(None))
            .distinct()
        )
        result = await session.execute(stmt)
        return {row[0]: (row[1], row[2]) for row in result.all()}


async def get_preferred_store_ids() -> dict[str, set[str]]:
    """Load user store preferences grouped by SKU.

    Returns {sku: {store_id, ...}} — only for watched, non-delisted products.
    """
    async with _SessionLocal() as session:
        stmt = (
            select(Watch.sku, UserStorePreference.saq_store_id)
            .join(Product, Watch.sku == Product.sku)
            .join(UserStorePreference, Watch.user_id == UserStorePreference.user_id)
            .where(Product.delisted_at.is_(None))
        )
        result = await session.execute(stmt)
        prefs: dict[str, set[str]] = {}
        for sku, store_id in result.all():
            prefs.setdefault(sku, set()).add(store_id)
        return prefs


async def upsert_stores(stores: list[StoreData]) -> None:
    """Bulk upsert stores into the database."""
    if not stores:
        return

    now = datetime.now(UTC)
    values_list = [{**asdict(store), "created_at": now} for store in stores]

    # Preserve created_at on re-runs — same semantics as Product.created_at
    update_cols = [c for c in values_list[0] if c not in ("saq_store_id", "created_at")]

    async with _SessionLocal() as session:
        stmt = pg_insert(Store).values(values_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=list(Store.__table__.primary_key),
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        try:
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).error("DB error upserting {} stores", len(stores))
            raise

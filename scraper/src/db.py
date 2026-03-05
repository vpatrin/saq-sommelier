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
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .products import ProductData
from .stores import StoreData

_SessionLocal = create_session_factory(settings.database_url, settings.database_echo)


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


async def get_watchable_skus() -> list[str]:
    """Get watched SKUs for non-delisted products — used by --availability-check (Phase 6)."""
    async with _SessionLocal() as session:
        stmt = (
            select(Watch.sku)
            .join(Product, Watch.sku == Product.sku)
            .where(Product.delisted_at.is_(None))
            .distinct()
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


async def get_watched_store_coords() -> dict[str, tuple[float, float]]:
    """Get coordinates for all stores in user preferences — used by --availability-check (Phase 6).

    Returns {saq_store_id: (latitude, longitude)} for stores that have coordinates.
    """
    async with _SessionLocal() as session:
        stmt = (
            select(Store.saq_store_id, Store.latitude, Store.longitude)
            .join(
                UserStorePreference,
                Store.saq_store_id == UserStorePreference.saq_store_id,
            )
            .where(Store.latitude.isnot(None), Store.longitude.isnot(None))
            .distinct()
        )
        result = await session.execute(stmt)
        return {row[0]: (row[1], row[2]) for row in result.all()}


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

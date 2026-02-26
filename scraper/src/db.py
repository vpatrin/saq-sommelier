from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from core.db.base import create_session_factory
from core.db.models import Product, StockEvent, Store
from loguru import logger
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .products import ProductData
from .stores import StoreData

_SessionLocal = create_session_factory(settings.database_url, settings.database_echo)


async def stores_populated() -> bool:
    """Return True if the stores table has at least one row."""
    async with _SessionLocal() as session:
        result = await session.execute(select(Store.saq_store_id).limit(1))
        return result.first() is not None


async def get_updated_dates() -> dict[str, date]:
    """Fetch the last-updated date for every product in the DB."""
    async with _SessionLocal() as session:
        stmt = select(Product.sku, Product.updated_at)
        result = await session.execute(stmt)
        return {sku: updated_at.date() for sku, updated_at in result.all()}


async def get_availability_map() -> dict[str, bool | None]:
    """Fetch current availability for every product in the DB."""
    async with _SessionLocal() as session:
        stmt = select(Product.sku, Product.availability)
        result = await session.execute(stmt)
        return dict(result.all())


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


async def emit_stock_event(sku: str, available: bool) -> None:
    """Record an availability transition in the stock_events table.

    Swallows errors — a missed event shouldn't crash the scraper.
    """
    async with _SessionLocal() as session:
        stmt = pg_insert(StockEvent).values(sku=sku, available=available)
        try:
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.error("Failed to emit stock event for SKU {}", sku)


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
        except SQLAlchemyError:
            await session.rollback()
            logger.error("Stock event cleanup failed, skipping")


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
        product_dict["created_at"] = datetime.now(UTC)
        product_dict["updated_at"] = datetime.now(UTC)

        stmt = pg_insert(Product).values(product_dict)

        # On conflict (SKU already exists), update all fields except sku and created_at
        update_dict = {k: v for k, v in product_dict.items() if k not in ["sku", "created_at"]}
        update_dict["updated_at"] = datetime.now(UTC)

        stmt = stmt.on_conflict_do_update(
            index_elements=list(Product.__table__.primary_key),
            set_=update_dict,  # Update these fields
        )

        try:
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.error("DB error upserting SKU {}", product_data.sku or "unknown")
            raise


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
        except SQLAlchemyError:
            await session.rollback()
            logger.error("DB error upserting {} stores", len(stores))
            raise

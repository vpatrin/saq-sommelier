from datetime import UTC, date, datetime

from core.db.base import create_session_factory
from core.db.models import Product
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .parser import ProductData

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
        product_dict = product_data.to_dict()
        product_dict["created_at"] = datetime.now(UTC)
        product_dict["updated_at"] = datetime.now(UTC)

        stmt = pg_insert(Product).values(product_dict)

        # On conflict (SKU already exists), update all fields except sku and created_at
        update_dict = {k: v for k, v in product_dict.items() if k not in ["sku", "created_at"]}
        update_dict["updated_at"] = datetime.now(UTC)

        stmt = stmt.on_conflict_do_update(
            index_elements=["sku"],  # Conflict on primary key (sku)
            set_=update_dict,  # Update these fields
        )

        try:
            await session.execute(stmt)
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.error("DB error upserting SKU {}", product_data.sku or "unknown")
            raise

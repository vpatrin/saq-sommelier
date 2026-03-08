from dataclasses import asdict
from datetime import UTC, date, datetime

from core.db.models import Product
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from ..products import ProductData
from .session import SessionLocal


async def get_all_skus() -> set[str]:
    """Return the set of all product SKUs in the DB."""
    async with SessionLocal() as session:
        result = await session.execute(select(Product.sku))
        return {row[0] for row in result.all()}


async def get_updated_dates() -> dict[str, date]:
    """Fetch the last-updated date for every product in the DB."""
    async with SessionLocal() as session:
        stmt = select(Product.sku, Product.updated_at)
        result = await session.execute(stmt)
        return {sku: updated_at.date() for sku, updated_at in result.all()}


async def get_delisted_skus() -> set[str]:
    """Get SKUs of products currently marked as delisted."""
    async with SessionLocal() as session:
        stmt = select(Product.sku).where(Product.delisted_at.isnot(None))
        result = await session.execute(stmt)
        return {row[0] for row in result.all()}


async def mark_delisted(skus: set[str]) -> int:
    """Set delisted_at on given SKUs. Returns count updated."""
    if not skus:
        return 0
    async with SessionLocal() as session:
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
    async with SessionLocal() as session:
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

    Uses PostgreSQL's INSERT ON CONFLICT DO UPDATE (upsert).
    """
    async with SessionLocal() as session:
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
            set_=update_dict,
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

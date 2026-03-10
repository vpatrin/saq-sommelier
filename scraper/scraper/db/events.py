from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from core.db.models import StockEvent, Watch

from .session import SessionLocal


async def get_watched_skus() -> list[str]:
    """Get all distinct SKUs from the watches table."""
    async with SessionLocal() as session:
        stmt = select(Watch.sku).distinct()
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


async def emit_stock_event(sku: str, available: bool, *, saq_store_id: str | None = None) -> None:
    """Record an availability transition in the stock_events table.

    saq_store_id: NULL = online event, non-NULL = in-store event.
    """
    async with SessionLocal() as session:
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
    async with SessionLocal() as session:
        stmt = delete(StockEvent).where(StockEvent.detected_at < cutoff)
        try:
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount:
                logger.info("Purged {} stock events older than {} days", result.rowcount, days)
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.opt(exception=exc).warning("Stock event cleanup failed, skipping")

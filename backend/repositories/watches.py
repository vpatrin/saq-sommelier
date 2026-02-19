from datetime import UTC, datetime

from core.db.models import Product, RestockEvent, Watch
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import MAX_ACK_BATCH_SIZE


async def create(db: AsyncSession, user_id: str, sku: str) -> Watch:
    """Insert a new watch. Caller must handle IntegrityError for duplicates."""
    watch = Watch(user_id=user_id, sku=sku)
    db.add(watch)
    await db.flush()
    await db.refresh(watch)
    return watch


async def find_by_user(db: AsyncSession, user_id: str) -> list[tuple[Watch, Product | None]]:
    """Return all watches for a user, with their product data (LEFT JOIN)."""
    stmt = (
        select(Watch, Product)
        .outerjoin(Product, Watch.sku == Product.sku)
        .where(Watch.user_id == user_id)
        .order_by(Watch.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.all())


async def find_one(db: AsyncSession, user_id: str, sku: str) -> Watch | None:
    """Return a single watch by user_id + sku, or None."""
    stmt = select(Watch).where(Watch.user_id == user_id, Watch.sku == sku)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete(db: AsyncSession, watch: Watch) -> None:
    """Delete a watch."""
    await db.delete(watch)
    await db.flush()


async def find_pending_notifications(
    db: AsyncSession,
) -> list[tuple[RestockEvent, Watch, Product | None]]:
    """Return all pending restock notifications (events x watches), with product data."""
    stmt = (
        select(RestockEvent, Watch, Product)
        # Only events where someone is watching that SKU
        .join(Watch, RestockEvent.sku == Watch.sku)
        # Attach product info if available
        .outerjoin(Product, RestockEvent.sku == Product.sku)
        # Skip already-notified events
        .where(RestockEvent.processed_at.is_(None))
        # Only "back in stock" events
        .where(RestockEvent.available.is_(True))
        # Oldest first (FIFO)
        .order_by(RestockEvent.detected_at.asc())
        # Match MAX_ACK_BATCH_SIZE — bot can ack everything it receives in one call
        .limit(MAX_ACK_BATCH_SIZE)
    )
    result = await db.execute(stmt)
    return list(result.all())


async def ack_events(db: AsyncSession, event_ids: list[int]) -> int:
    """Mark events as processed. Returns count of rows actually updated."""
    stmt = (
        update(RestockEvent)
        .where(RestockEvent.id.in_(event_ids))
        .where(RestockEvent.processed_at.is_(None))
        .values(processed_at=datetime.now(UTC))
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount

from datetime import UTC, datetime

from sqlalchemy import and_, select, update
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import MAX_ACK_BATCH_SIZE
from core.db.models import Product, StockEvent, Store, UserStorePreference, Watch


async def create(db: AsyncSession, user_id: str, sku: str) -> Watch:
    """Insert a new watch. Caller must handle IntegrityError for duplicates."""
    watch = Watch(user_id=user_id, sku=sku)
    db.add(watch)
    await db.flush()
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
) -> list[tuple[StockEvent, Watch, Product | None, Store | None]]:
    """Return pending notifications — online to all watchers, store to preference matches."""
    # Online events (saq_store_id IS NULL) — notify all watchers
    online_stmt = (
        select(StockEvent, Watch, Product)
        .join(Watch, StockEvent.sku == Watch.sku)
        .outerjoin(Product, StockEvent.sku == Product.sku)
        .where(StockEvent.processed_at.is_(None))
        .where(StockEvent.saq_store_id.is_(None))
        .order_by(StockEvent.detected_at.asc())
        .limit(MAX_ACK_BATCH_SIZE)
    )
    online_rows = (await db.execute(online_stmt)).all()

    # Store events (saq_store_id IS NOT NULL) — route via UserStorePreference
    store_stmt = (
        select(StockEvent, Watch, Product, Store)
        .join(Watch, StockEvent.sku == Watch.sku)
        .join(
            UserStorePreference,
            and_(
                Watch.user_id == UserStorePreference.user_id,
                StockEvent.saq_store_id == UserStorePreference.saq_store_id,
            ),
        )
        .outerjoin(Product, StockEvent.sku == Product.sku)
        .outerjoin(Store, StockEvent.saq_store_id == Store.saq_store_id)
        .where(StockEvent.processed_at.is_(None))
        .where(StockEvent.saq_store_id.isnot(None))
        .order_by(StockEvent.detected_at.asc())
        .limit(MAX_ACK_BATCH_SIZE)
    )
    store_rows = (await db.execute(store_stmt)).all()

    # Merge: pad online rows with None store to match unified return type
    results: list[tuple[StockEvent, Watch, Product | None, Store | None]] = [
        (event, watch, product, None) for event, watch, product in online_rows
    ]
    results.extend(store_rows)
    results.sort(key=lambda r: r[0].detected_at)
    return results[:MAX_ACK_BATCH_SIZE]


async def delete_by_delisted_event_ids(db: AsyncSession, event_ids: list[int]) -> int:
    """Delete watches for any SKU that is delisted and referenced in the given event IDs.

    Deletes across ALL users — a delisted product has no meaningful watch state for anyone.
    Returns count of watches deleted.
    """
    sku_stmt = (
        select(StockEvent.sku)
        .join(Product, StockEvent.sku == Product.sku)
        .where(StockEvent.id.in_(event_ids))
        .where(Product.delisted_at.isnot(None))
        .distinct()
    )
    result = await db.execute(sku_stmt)
    delisted_skus = [row[0] for row in result.all()]

    if not delisted_skus:
        return 0

    stmt = sa_delete(Watch).where(Watch.sku.in_(delisted_skus))
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount


async def ack_events(db: AsyncSession, event_ids: list[int]) -> int:
    """Mark events as processed. Returns count of rows actually updated."""
    stmt = (
        update(StockEvent)
        .where(StockEvent.id.in_(event_ids))
        .where(StockEvent.processed_at.is_(None))
        .values(processed_at=datetime.now(UTC))
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount

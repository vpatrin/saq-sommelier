from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import ConflictError, NotFoundError
from backend.repositories import products as products_repo
from backend.repositories import watches as repo
from backend.schemas.product import ProductOut
from backend.schemas.watch import PendingNotification, WatchOut, WatchWithProduct


async def create_watch(db: AsyncSession, user_id: str, sku: str) -> WatchWithProduct:
    """Create a watch. Raises ConflictError if already exists, NotFoundError if SKU invalid."""
    try:
        watch = await repo.create(db, user_id, sku)
    except IntegrityError as exc:
        await db.rollback()
        error_msg = str(exc.orig) if exc.orig else str(exc)
        if "uq_watches_user_sku" in error_msg:
            raise ConflictError("Watch", f"user {user_id!r} already watches SKU {sku!r}") from exc
        # Assumed FK violation — SKU doesn't exist in products table.
        # Log in case a future constraint triggers this path unexpectedly.
        logger.warning(
            "IntegrityError on watch create (sku={}, constraint not uq_watches_user_sku): {}",
            sku,
            error_msg,
        )
        raise NotFoundError("Product", sku) from exc
    product = await products_repo.find_by_sku(db, sku)
    return WatchWithProduct(
        watch=WatchOut.model_validate(watch),
        product=ProductOut.model_validate(product) if product else None,
    )


async def list_watches(db: AsyncSession, user_id: str) -> list[WatchWithProduct]:
    """Return all watches for a user, with product data."""
    rows = await repo.find_by_user(db, user_id)
    return [
        WatchWithProduct(
            watch=WatchOut.model_validate(watch),
            product=ProductOut.model_validate(product) if product else None,
        )
        for watch, product in rows
    ]


async def delete_watch(db: AsyncSession, user_id: str, sku: str) -> None:
    """Delete a watch. Raises NotFoundError if it doesn't exist."""
    watch = await repo.find_one(db, user_id, sku)
    if watch is None:
        raise NotFoundError("Watch", sku)
    await repo.delete(db, watch)


async def list_pending_notifications(db: AsyncSession) -> list[PendingNotification]:
    """Return all pending stock event notifications across all users."""
    rows = await repo.find_pending_notifications(db)
    return [
        PendingNotification(
            event_id=event.id,
            sku=event.sku,
            user_id=watch.user_id,
            available=event.available,
            product_name=product.name if product else None,
            detected_at=event.detected_at,
            saq_store_id=event.saq_store_id,
            store_name=store.name if store else None,
            online_available=product.availability if product else None,
        )
        for event, watch, product, store in rows
    ]


async def ack_notifications(db: AsyncSession, event_ids: list[int]) -> int:
    """Mark stock events as processed. Returns count acked."""
    count = await repo.ack_events(db, event_ids)
    if count < len(event_ids):
        logger.warning("Acked {}/{} events (rest already processed)", count, len(event_ids))
    return count

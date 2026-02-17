from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import ConflictError, NotFoundError
from backend.repositories import watches as repo
from backend.schemas.product import ProductResponse
from backend.schemas.watch import WatchResponse, WatchWithProduct


async def create_watch(db: AsyncSession, user_id: str, sku: str) -> WatchResponse:
    """Create a watch. Raises ConflictError if already exists, NotFoundError if SKU invalid."""
    try:
        watch = await repo.create(db, user_id, sku)
    except IntegrityError as exc:
        await db.rollback()
        error_msg = str(exc.orig) if exc.orig else str(exc)
        if "uq_watches_user_sku" in error_msg:
            raise ConflictError("Watch", f"user {user_id!r} already watches SKU {sku!r}") from exc
        # FK violation — SKU doesn't exist in products table
        raise NotFoundError("Product", sku) from exc
    return WatchResponse.model_validate(watch)


async def list_watches(db: AsyncSession, user_id: str) -> list[WatchWithProduct]:
    """Return all watches for a user, with product data."""
    rows = await repo.find_by_user(db, user_id)
    return [
        WatchWithProduct(
            watch=WatchResponse.model_validate(watch),
            product=ProductResponse.model_validate(product) if product else None,
        )
        for watch, product in rows
    ]


async def delete_watch(db: AsyncSession, user_id: str, sku: str) -> None:
    """Delete a watch. Raises NotFoundError if it doesn't exist."""
    watch = await repo.find_one(db, user_id, sku)
    if watch is None:
        raise NotFoundError("Watch", sku)
    await repo.delete(db, watch)

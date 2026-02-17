from core.db.models import Product, Watch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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

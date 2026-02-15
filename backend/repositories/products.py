from shared.db.models import Product
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def count(db: AsyncSession) -> int:
    """Return the total number of products."""
    result = await db.execute(select(func.count()).select_from(Product))
    return result.scalar_one()


async def find_page(db: AsyncSession, offset: int, limit: int) -> list[Product]:
    """Return a page of products ordered by name."""
    result = await db.execute(select(Product).order_by(Product.name).offset(offset).limit(limit))
    return list(result.scalars().all())

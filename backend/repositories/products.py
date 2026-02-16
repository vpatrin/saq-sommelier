from decimal import Decimal

from core.db.models import Product
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _apply_filters(
    stmt: Select,
    *,
    q: str | None = None,
    category: str | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
) -> Select:
    """Append WHERE clauses for each non-None filter."""
    if q is not None:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if category is not None:
        stmt = stmt.where(Product.category == category)
    if country is not None:
        stmt = stmt.where(Product.country == country)
    if region is not None:
        stmt = stmt.where(Product.region == region)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    return stmt


async def count(
    db: AsyncSession,
    *,
    q: str | None = None,
    category: str | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
) -> int:
    """Return the total number of products matching the given filters."""
    stmt = select(func.count()).select_from(Product)
    stmt = _apply_filters(
        stmt,
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def find_by_sku(db: AsyncSession, sku: str) -> Product | None:
    """Return a single product by SKU, or None if not found."""
    result = await db.execute(select(Product).where(Product.sku == sku))
    return result.scalar_one_or_none()


async def find_page(
    db: AsyncSession,
    offset: int,
    limit: int,
    *,
    q: str | None = None,
    category: str | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
) -> list[Product]:
    """Return a page of products ordered by name, with optional filters."""
    stmt = select(Product).order_by(Product.name).offset(offset).limit(limit)
    stmt = _apply_filters(
        stmt,
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

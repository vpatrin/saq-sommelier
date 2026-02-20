from decimal import Decimal

from core.db.models import Product
from sqlalchemy import Column, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

_SORT_ORDERS = {
    "recent": Product.updated_at.desc(),
    "price_asc": Product.price.asc(),
    "price_desc": Product.price.desc(),
}


def _apply_filters(
    stmt: Select,
    *,
    q: str | None = None,
    category: list[str] | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
) -> Select:
    """Append WHERE clauses for each non-None filter."""
    # Always exclude delisted products (page gone from SAQ sitemap)
    stmt = stmt.where(Product.delisted_at.is_(None))
    if available is not None:
        stmt = stmt.where(Product.availability == available)  # noqa: E712
    if q is not None:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if category is not None:
        stmt = stmt.where(Product.category.in_(category))
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
    category: list[str] | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
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
        available=available,
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def find_by_sku(db: AsyncSession, sku: str) -> Product | None:
    """Return a single non-delisted product by SKU, or None if not found."""
    stmt = select(Product).where(Product.sku == sku).where(Product.delisted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_page(
    db: AsyncSession,
    offset: int,
    limit: int,
    *,
    sort: str | None = None,
    q: str | None = None,
    category: list[str] | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
) -> list[Product]:
    """Return a page of products with optional filters and sorting."""
    order = _SORT_ORDERS.get(sort, Product.name)
    stmt = select(Product).order_by(order).offset(offset).limit(limit)
    stmt = _apply_filters(
        stmt,
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_distinct_values(db: AsyncSession, column: Column) -> list[str]:
    """Return sorted distinct non-null values for a product column (active products only)."""
    stmt = (
        select(column)
        .where(Product.delisted_at.is_(None))
        .where(column.isnot(None))
        .distinct()
        .order_by(column)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def find_random(
    db: AsyncSession,
    *,
    category: list[str] | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
) -> Product | None:
    """Return a single random product matching the given filters, or None."""
    stmt = select(Product).order_by(func.random()).limit(1)
    stmt = _apply_filters(
        stmt,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_price_range(db: AsyncSession) -> tuple[Decimal, Decimal] | None:
    """Return (min, max) price for active products, or None if no prices exist."""
    stmt = (
        select(func.min(Product.price), func.max(Product.price))
        .where(Product.delisted_at.is_(None))
        .where(Product.price.isnot(None))
    )
    result = await db.execute(stmt)
    row = result.one()
    if row[0] is None:
        return None
    return (row[0], row[1])

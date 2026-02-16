import math
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import NotFoundError
from backend.repositories.products import count, find_by_sku, find_page
from backend.schemas.product import PaginatedResponse, ProductResponse


async def get_product(db: AsyncSession, sku: str) -> ProductResponse:
    """Fetch a single product by SKU. Raises NotFoundError if not found."""
    product = await find_by_sku(db, sku)
    if product is None:
        raise NotFoundError("Product", sku)
    return ProductResponse.model_validate(product)


async def list_products(
    db: AsyncSession,
    page: int,
    per_page: int,
    *,
    q: str | None = None,
    category: str | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
) -> PaginatedResponse:
    """Fetch a paginated list of products, optionally filtered."""
    filters = dict(
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
    )
    total = await count(db, **filters)

    offset = (page - 1) * per_page
    rows = await find_page(db, offset, per_page, **filters)

    return PaginatedResponse(
        products=[ProductResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )

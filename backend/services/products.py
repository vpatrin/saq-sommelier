import math
from decimal import Decimal

from core.db.models import Product
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import NotFoundError
from backend.repositories.products import (
    count,
    find_by_sku,
    find_page,
    find_random,
    get_distinct_values,
    get_price_range,
)
from backend.schemas.product import (
    FacetsResponse,
    PaginatedResponse,
    PriceRange,
    ProductResponse,
)


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
    sort: str | None = None,
    q: str | None = None,
    category: str | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
) -> PaginatedResponse:
    """Fetch a paginated list of products, optionally filtered and sorted."""
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
    rows = await find_page(db, offset, per_page, sort=sort, **filters)

    return PaginatedResponse(
        products=[ProductResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )


async def get_random_product(
    db: AsyncSession,
    *,
    category: str | None = None,
    country: str | None = None,
    region: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
) -> ProductResponse:
    """Fetch a single random product matching filters. Raises NotFoundError if none."""
    product = await find_random(
        db,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
    )
    if product is None:
        raise NotFoundError("Product", "random")
    return ProductResponse.model_validate(product)


async def get_facets(db: AsyncSession) -> FacetsResponse:
    """Fetch distinct filter values and price range for active products."""
    categories = await get_distinct_values(db, Product.category)
    countries = await get_distinct_values(db, Product.country)
    regions = await get_distinct_values(db, Product.region)
    grapes = await get_distinct_values(db, Product.grape)
    price_result = await get_price_range(db)

    return FacetsResponse(
        categories=categories,
        countries=countries,
        regions=regions,
        grapes=grapes,
        price_range=PriceRange(min=price_result[0], max=price_result[1]) if price_result else None,
    )

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import (
    DEFAULT_LIMIT,
    MAX_FILTER_LENGTH,
    MAX_LIMIT,
    MAX_SAQ_STORE_ID_LENGTH,
    MAX_SEARCH_LENGTH,
    MAX_SKU_LENGTH,
)
from backend.db import get_db
from backend.schemas.product import FacetsOut, PaginatedOut, ProductOut
from backend.services.products import get_facets, get_product, get_random_product, list_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=PaginatedOut)
async def get_products(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    sort: Literal["recent", "price_asc", "price_desc", "alpha"] | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=MAX_SEARCH_LENGTH),
    category: list[Annotated[str, Query(max_length=MAX_FILTER_LENGTH)]] | None = Query(
        default=None
    ),
    country: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    region: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    available: bool | None = Query(default=None),
    in_stores: list[Annotated[str, Query(max_length=MAX_SAQ_STORE_ID_LENGTH)]] | None = Query(
        default=None
    ),
    scope: Literal["wine", "all"] = Query(default="wine"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedOut:
    """List products with offset-based pagination and optional filters and sorting options."""
    return await list_products(
        db,
        limit,
        offset,
        sort=sort,
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
        in_stores=in_stores,
        wine_scope=scope == "wine",
    )


@router.get("/facets", response_model=FacetsOut)
async def get_product_facets(
    category: list[Annotated[str, Query(max_length=MAX_FILTER_LENGTH)]] | None = Query(
        default=None
    ),
    available: bool | None = Query(default=None),
    in_stores: list[Annotated[str, Query(max_length=MAX_SAQ_STORE_ID_LENGTH)]] | None = Query(
        default=None
    ),
    scope: Literal["wine", "all"] = Query(default="wine"),
    db: AsyncSession = Depends(get_db),
) -> FacetsOut:
    """Return distinct filter values and price range for the catalog."""
    return await get_facets(
        db,
        category=category,
        available=available,
        in_stores=in_stores,
        wine_scope=scope == "wine",
    )


@router.get("/random", response_model=ProductOut)
async def get_random(
    category: list[Annotated[str, Query(max_length=MAX_FILTER_LENGTH)]] | None = Query(
        default=None
    ),
    country: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    region: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    available: bool | None = Query(default=None),
    in_stores: list[Annotated[str, Query(max_length=MAX_SAQ_STORE_ID_LENGTH)]] | None = Query(
        default=None
    ),
    scope: Literal["wine", "all"] = Query(default="wine"),
    db: AsyncSession = Depends(get_db),
) -> ProductOut:
    """Return a single random product matching the given filters."""
    return await get_random_product(
        db,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
        in_stores=in_stores,
        wine_scope=scope == "wine",
    )


@router.get("/{sku}", response_model=ProductOut)
async def get_product_detail(
    sku: str = Path(max_length=MAX_SKU_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> ProductOut:
    """Get a single product by SKU."""
    return await get_product(db, sku)

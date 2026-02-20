from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import (
    DEFAULT_PAGE_SIZE,
    MAX_FILTER_LENGTH,
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
    MAX_SKU_LENGTH,
)
from backend.db import get_db
from backend.schemas.product import FacetsResponse, PaginatedResponse, ProductResponse
from backend.services.products import get_facets, get_product, get_random_product, list_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=PaginatedResponse)
async def get_products(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    sort: Literal["recent", "price_asc", "price_desc"] | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=MAX_SEARCH_LENGTH),
    category: list[str] | None = Query(default=None),
    country: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    region: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    available: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List products with offset-based pagination and optional filters and sorting options."""
    return await list_products(
        db,
        page,
        per_page,
        sort=sort,
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
    )


@router.get("/facets", response_model=FacetsResponse)
async def get_product_facets(
    db: AsyncSession = Depends(get_db),
) -> FacetsResponse:
    """Return distinct filter values and price range for the catalog."""
    return await get_facets(db)


@router.get("/random", response_model=ProductResponse)
async def get_random(
    category: list[str] | None = Query(default=None),
    country: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    region: str | None = Query(default=None, max_length=MAX_FILTER_LENGTH),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    available: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Return a single random product matching the given filters."""
    return await get_random_product(
        db,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
        available=available,
    )


@router.get("/{sku}", response_model=ProductResponse)
async def get_product_detail(
    sku: str = Path(max_length=MAX_SKU_LENGTH),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Get a single product by SKU."""
    return await get_product(db, sku)

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.db import get_db
from backend.schemas.product import PaginatedResponse, ProductResponse
from backend.services.products import get_product, list_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=PaginatedResponse)
async def get_products(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(default=None, min_length=1, description="Search product name"),
    category: str | None = Query(default=None),
    country: str | None = Query(default=None),
    region: str | None = Query(default=None),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List products with offset-based pagination and optional filters."""
    return await list_products(
        db,
        page,
        per_page,
        q=q,
        category=category,
        country=country,
        region=region,
        min_price=min_price,
        max_price=max_price,
    )


@router.get("/{sku}", response_model=ProductResponse)
async def get_product_detail(
    sku: str,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Get a single product by SKU."""
    return await get_product(db, sku)

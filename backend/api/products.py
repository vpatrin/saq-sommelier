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
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List products with offset-based pagination."""
    return await list_products(db, page, per_page)


@router.get("/{sku}", response_model=ProductResponse)
async def get_product_detail(
    sku: str,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Get a single product by SKU."""
    return await get_product(db, sku)

import math

from fastapi import APIRouter, Depends, Query
from shared.db.models import Product
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.db import get_db
from backend.schemas.product import PaginatedResponse, ProductResponse

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=PaginatedResponse)
async def list_products(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List products with offset-based pagination."""
    # Count total products
    total = (await db.execute(select(func.count()).select_from(Product))).scalar_one()

    # Fetch page
    offset = (page - 1) * per_page
    rows = (
        (await db.execute(select(Product).order_by(Product.name).offset(offset).limit(per_page)))
        .scalars()
        .all()
    )

    return PaginatedResponse(
        products=[ProductResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )

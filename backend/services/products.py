import math

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.products import count, find_page
from backend.schemas.product import PaginatedResponse, ProductResponse


async def list_products(
    db: AsyncSession,
    page: int,
    per_page: int,
) -> PaginatedResponse:
    """Fetch a paginated list of products ordered by name."""
    total = await count(db)

    offset = (page - 1) * per_page
    rows = await find_page(db, offset, per_page)

    return PaginatedResponse(
        products=[ProductResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )

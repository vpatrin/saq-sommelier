from core.db.models import Product
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import DEFAULT_RECOMMENDATION_LIMIT
from backend.schemas.recommendation import IntentResult


async def find_similar(
    db: AsyncSession,
    intent: IntentResult,
    query_embedding: list[float],
    *,
    limit: int = DEFAULT_RECOMMENDATION_LIMIT,
) -> list[Product]:
    """Return products matching structured filters, ranked by embedding similarity."""
    stmt = select(Product).where(Product.delisted_at.is_(None)).where(Product.embedding.isnot(None))

    if intent.categories:
        stmt = stmt.where(Product.category.in_(intent.categories))
    if intent.country is not None:
        stmt = stmt.where(Product.country == intent.country)
    if intent.min_price is not None:
        stmt = stmt.where(Product.price >= intent.min_price)
    if intent.max_price is not None:
        stmt = stmt.where(Product.price <= intent.max_price)
    if intent.available_only:
        stmt = stmt.where(Product.online_availability.is_(True))

    # Similarity ranking
    stmt = stmt.order_by(Product.embedding.cosine_distance(query_embedding)).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())

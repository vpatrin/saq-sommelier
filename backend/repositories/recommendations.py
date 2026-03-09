from core.categories import expand_family
from core.db.models import Product
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import DEFAULT_RECOMMENDATION_LIMIT
from backend.schemas.recommendation import IntentResult

# Default to wine categories when intent has no category filter
_WINE_PREFIXES: list[str] = expand_family("vins", None)

# Over-fetch multiplier — fetch more candidates than needed, then rerank for diversity
_DIVERSITY_POOL = 5


async def find_similar(
    db: AsyncSession,
    intent: IntentResult,
    query_embedding: list[float],
    *,
    available_online: bool = True,
    in_store: str | None = None,
    limit: int = DEFAULT_RECOMMENDATION_LIMIT,
) -> list[Product]:
    """Return products matching structured filters, ranked by embedding similarity."""
    stmt = select(Product).where(Product.delisted_at.is_(None)).where(Product.embedding.isnot(None))

    if intent.categories:
        stmt = stmt.where(Product.category.in_(intent.categories))
    else:
        # No category from intent → default to wines (same as product list scope=wine)
        stmt = stmt.where(or_(*(Product.category.startswith(p) for p in _WINE_PREFIXES)))
    if intent.country is not None:
        stmt = stmt.where(Product.country == intent.country)
    if intent.min_price is not None:
        stmt = stmt.where(Product.price >= intent.min_price)
    if intent.max_price is not None:
        stmt = stmt.where(Product.price <= intent.max_price)
    # Always exclude products with no price — $0 items drag down value scores
    stmt = stmt.where(Product.price > 0)
    if intent.exclude_grapes:
        for grape in intent.exclude_grapes:
            # Exclude wines whose grape or grape_blend contains the unwanted variety
            stmt = stmt.where(~Product.grape.ilike(f"%{grape}%") | Product.grape.is_(None))
    if available_online:
        stmt = stmt.where(Product.online_availability.is_(True))
    if in_store is not None:
        stmt = stmt.where(Product.store_availability.contains([in_store]))
    # Over-fetch for producer diversity, then deduplicate
    stmt = stmt.order_by(Product.embedding.cosine_distance(query_embedding)).limit(
        limit * _DIVERSITY_POOL
    )

    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    return _rerank(candidates, limit)


# Redundancy penalty weight — higher = more diversity, lower = more relevance
_DIVERSITY_LAMBDA = 0.5


def _rerank(candidates: list[Product], limit: int) -> list[Product]:
    """Greedy MMR-style selection: balance relevance (embedding rank) with diversity.

    Each candidate gets a score = relevance_score - λ * redundancy_penalty.
    Relevance score decays with position (1st candidate = 1.0, last = ~0.0).
    Redundancy penalty increases when a candidate shares attributes with already-selected wines.
    """
    if len(candidates) <= limit:
        return candidates

    n = len(candidates)
    selected: list[Product] = []
    remaining = list(range(n))

    # Always pick the top-ranked candidate first (highest embedding similarity)
    selected_idx = remaining.pop(0)
    selected.append(candidates[selected_idx])

    while len(selected) < limit and remaining:
        best_score = -float("inf")
        best_idx_pos = 0

        for pos, idx in enumerate(remaining):
            candidate = candidates[idx]
            relevance = 1.0 - (idx / n)
            redundancy = _redundancy_penalty(candidate, selected)
            score = relevance - _DIVERSITY_LAMBDA * redundancy
            if score > best_score:
                best_score = score
                best_idx_pos = pos

        chosen = remaining.pop(best_idx_pos)
        selected.append(candidates[chosen])

    return selected


def _redundancy_penalty(candidate: Product, selected: list[Product]) -> float:
    """Score measuring how redundant this candidate is with already-selected wines.

    Base overlap is 0-1 per selected wine, boosted by how many are similar (can exceed 1.0).
    """
    if not selected:
        return 0.0

    penalties: list[float] = []
    for s in selected:
        overlap = 0.0
        checks = 0.0

        # Same producer is a strong signal of redundancy
        if candidate.producer and s.producer:
            checks += 1.5
            if candidate.producer == s.producer:
                overlap += 1.5

        # Same taste profile tag = similar flavor experience
        if candidate.taste_tag and s.taste_tag:
            checks += 1.0
            if candidate.taste_tag == s.taste_tag:
                overlap += 1.0

        # Same country = less geographic diversity
        if candidate.country and s.country:
            checks += 0.5
            if candidate.country == s.country:
                overlap += 0.5

        # Same grape = less varietal diversity
        if candidate.grape and s.grape:
            checks += 1.0
            if candidate.grape == s.grape:
                overlap += 1.0

        # Same region = very similar terroir
        if candidate.region and s.region:
            checks += 1.0
            if candidate.region == s.region:
                overlap += 1.0

        # Same category (e.g. all whites) = less type diversity
        if candidate.category and s.category:
            checks += 0.75
            if candidate.category == s.category:
                overlap += 0.75

        penalties.append(overlap / checks if checks > 0 else 0.0)

    # Accumulating penalty: each additional similar wine makes the next one less desirable
    # max overlap provides the base, boosted by how many selected wines are similar
    max_p = max(penalties)
    similar_count = sum(1 for p in penalties if p > 0.3)
    return max_p * (1.0 + 0.2 * similar_count)

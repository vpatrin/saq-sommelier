from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_caller_user_id
from backend.config import MAX_LIMIT
from backend.db import get_db
from backend.schemas.tasting import TastingIn, TastingOut, TastingRatingOut, TastingUpdateIn
from backend.services.tastings import (
    create_tasting,
    delete_tasting,
    get_ratings_by_skus,
    list_tastings,
    update_tasting,
)

router = APIRouter(prefix="/tastings", tags=["tastings"])


@router.post("", response_model=TastingOut, status_code=status.HTTP_201_CREATED)
async def post_tasting(
    body: TastingIn,
    user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> TastingOut:
    """Log a tasting note for a wine."""
    return await create_tasting(
        db,
        user_id=user_id,
        sku=body.sku,
        rating=body.rating,
        notes=body.notes,
        pairing=body.pairing,
        tasted_at=body.tasted_at,
    )


@router.get("/ratings", response_model=dict[str, TastingRatingOut])
async def get_tasting_ratings(
    skus: str = Query(description="Comma-separated list of SKUs"),
    user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, TastingRatingOut]:
    """Return user ratings for the given SKUs. Only rated SKUs appear in the response."""
    sku_list = [s.strip() for s in skus.split(",") if s.strip()]
    if not sku_list:
        return {}
    return await get_ratings_by_skus(db, user_id=user_id, skus=sku_list)


@router.get("", response_model=list[TastingOut])
async def get_tastings(
    limit: int = Query(default=20, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TastingOut]:
    """List the authenticated user's tasting notes, reverse-chronological."""
    return await list_tastings(db, user_id=user_id, limit=limit, offset=offset)


@router.patch("/{note_id}", response_model=TastingOut)
async def patch_tasting(
    body: TastingUpdateIn,
    note_id: int = Path(ge=1),
    user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> TastingOut:
    """Update a tasting note. Only the owner can update."""
    return await update_tasting(
        db,
        user_id=user_id,
        note_id=note_id,
        rating=body.rating,
        notes=body.notes,
        pairing=body.pairing,
        tasted_at=body.tasted_at,
    )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tasting_endpoint(
    note_id: int = Path(ge=1),
    user_id: str | None = Depends(get_caller_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a tasting note. Only the owner can delete."""
    await delete_tasting(db, user_id=user_id, note_id=note_id)

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.schemas.recommendation import RecommendationIn, RecommendationOut
from backend.services.recommendations import recommend

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationOut)
async def post_recommendations(
    body: RecommendationIn,
    db: AsyncSession = Depends(get_db),
) -> RecommendationOut:
    return await recommend(
        db,
        body.query,
        user_id=body.user_id,
        available_online=body.available_online,
        in_store=body.in_store,
    )

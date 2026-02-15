from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Health check — verifies the API is up and the database is reachable."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}

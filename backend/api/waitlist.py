from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import RATE_LIMIT_WAITLIST
from backend.db import get_db
from backend.rate_limit import limiter
from backend.repositories import waitlist as waitlist_repo
from backend.schemas.waitlist import WaitlistIn

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post("", status_code=201)
@limiter.limit(RATE_LIMIT_WAITLIST)
async def request_access(
    request: Request, body: WaitlistIn, db: AsyncSession = Depends(get_db)
) -> None:
    """Submit a waitlist request. Always returns 200 — no enumeration of existing emails."""
    await waitlist_repo.create(db, email=body.email.lower())

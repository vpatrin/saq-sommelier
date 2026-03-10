from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.schemas.auth import TelegramLoginIn, TokenOut
from backend.services.auth import authenticate_telegram

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenOut)
async def login_telegram(
    body: TelegramLoginIn,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    return await authenticate_telegram(db, body)

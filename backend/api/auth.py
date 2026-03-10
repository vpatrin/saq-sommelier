from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_bot_secret
from backend.db import get_db
from backend.exceptions import ForbiddenError, NotFoundError
from backend.repositories import users as users_repo
from backend.schemas.auth import TelegramLoginIn, TokenOut
from backend.services.auth import authenticate_telegram

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenOut)
async def login_telegram(
    body: TelegramLoginIn,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    return await authenticate_telegram(db, body)


@router.get(
    "/telegram/check",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_bot_secret)],
)
async def check_user(
    telegram_id: int = Query(),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Check if a Telegram user is registered and active. Bot-secret only."""
    user = await users_repo.find_by_telegram_id(db, telegram_id)
    if not user:
        raise NotFoundError("User", str(telegram_id))
    if not user.is_active:
        raise ForbiddenError("Account is deactivated")

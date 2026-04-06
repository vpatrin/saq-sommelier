from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_active_user
from backend.db import get_db
from backend.exceptions import ConflictError, NotFoundError
from backend.repositories import oauth_accounts as oauth_accounts_repo
from backend.repositories import users as users_repo
from backend.schemas.auth import TelegramLoginIn
from backend.schemas.user import OAuthAccountOut, UserMeOut, UserUpdateSelfIn
from backend.services.auth import verify_telegram_data
from core.db.models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeOut)
async def get_me(
    user: User = Depends(get_current_active_user),
) -> User:
    return user


@router.patch("/me", status_code=status.HTTP_204_NO_CONTENT)
async def update_me(
    body: UserUpdateSelfIn,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Update the authenticated user's profile (partial — only sent fields are updated)."""
    if "display_name" in body.model_fields_set and body.display_name is not None:
        user.display_name = body.display_name
    if "locale" in body.model_fields_set:
        user.locale = body.locale
    await db.flush()


@router.get("/me/accounts", response_model=list[OAuthAccountOut])
async def list_accounts(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[OAuthAccountOut]:
    return await oauth_accounts_repo.list_by_user(db, user.id)


@router.delete("/me/accounts/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    provider: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect an OAuth provider. Cannot disconnect the last linked account."""
    count = await oauth_accounts_repo.count_by_user(db, user.id)
    if count <= 1:
        raise ConflictError("OAuthAccount", "cannot disconnect your only linked account")
    deleted = await oauth_accounts_repo.delete_by_user_and_provider(db, user.id, provider)
    if not deleted:
        raise NotFoundError("OAuthAccount", provider)


@router.get("/me/telegram")
async def get_telegram_status(
    user: User = Depends(get_current_active_user),
) -> dict[str, bool]:
    return {"linked": user.telegram_id is not None}


@router.post("/me/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def link_telegram(
    body: TelegramLoginIn,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Link a Telegram account for notifications."""
    verify_telegram_data(body)
    existing = await users_repo.find_by_telegram_id(db, body.id)
    if existing and existing.id != user.id:
        raise ConflictError("Telegram", "this Telegram account is linked to another user")
    await users_repo.link_telegram(db, user, body.id)


@router.delete("/me/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unlink Telegram account — stops notifications."""
    await users_repo.unlink_telegram(db, user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete the authenticated user and all associated data."""
    await users_repo.hard_delete(db, user)

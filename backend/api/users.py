from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_active_user
from backend.db import get_db
from backend.exceptions import ConflictError, NotFoundError
from backend.repositories import oauth_accounts as oauth_accounts_repo
from backend.repositories import users as users_repo
from backend.schemas.user import OAuthAccountOut, UserUpdateSelfIn
from core.db.models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", status_code=status.HTTP_204_NO_CONTENT)
async def update_me(
    body: UserUpdateSelfIn,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Update the authenticated user's profile."""
    user.display_name = body.display_name
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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete the authenticated user and all associated data."""
    await users_repo.hard_delete(db, user)

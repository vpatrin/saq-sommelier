from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_active_user
from backend.db import get_db
from backend.schemas.user import UserUpdateSelfIn
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

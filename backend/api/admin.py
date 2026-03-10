from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import verify_admin
from backend.config import ROLE_ADMIN
from backend.db import get_db
from backend.exceptions import ConflictError, NotFoundError
from backend.repositories import invites as invites_repo
from backend.repositories import users as users_repo
from backend.schemas.invite import InviteCodeOut
from backend.schemas.user import UserOut
from core.db.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/invites", response_model=InviteCodeOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> InviteCodeOut:
    invite = await invites_repo.create(db, created_by_id=user.id)
    await db.commit()
    return invite


@router.get("/invites", response_model=list[InviteCodeOut])
async def list_invites(db: AsyncSession = Depends(get_db)) -> list[InviteCodeOut]:
    return await invites_repo.list_all(db)


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    return await users_repo.list_all(db)


@router.post("/users/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db)) -> None:
    target_user = await users_repo.find_by_id(db, user_id)
    if target_user is None:
        raise NotFoundError("User", str(user_id))
    if target_user.role == ROLE_ADMIN:
        raise ConflictError("User", "cannot deactivate an admin")
    await users_repo.deactivate(db, user_id)
    await db.commit()

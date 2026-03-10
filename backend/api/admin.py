from core.db.models import User
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_active_user
from backend.db import get_db
from backend.repositories import invites as invites_repo
from backend.schemas.invite import InviteCodeOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/invites", response_model=InviteCodeOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InviteCodeOut:
    invite = await invites_repo.create(db, created_by_id=user.id)
    await db.commit()
    return invite


@router.get("/invites", response_model=list[InviteCodeOut])
async def list_invites(db: AsyncSession = Depends(get_db)) -> list[InviteCodeOut]:
    return await invites_repo.list_all(db)

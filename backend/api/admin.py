from fastapi import APIRouter, Depends, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import verify_admin
from backend.config import ROLE_ADMIN, WAITLIST_APPROVED
from backend.db import get_db
from backend.exceptions import ConflictError, NotFoundError
from backend.repositories import users as users_repo
from backend.repositories import waitlist as waitlist_repo
from backend.schemas.user import UserOut, UserUpdateIn
from backend.schemas.waitlist import WaitlistRequestOut
from backend.services.email import send_approval_email
from core.db.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    return await users_repo.list_all(db)


@router.patch("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(user_id: int, body: UserUpdateIn, db: AsyncSession = Depends(get_db)) -> None:
    target = await users_repo.find_by_id(db, user_id)
    if target is None:
        raise NotFoundError("User", str(user_id))
    if not body.is_active and target.role == ROLE_ADMIN:
        raise ConflictError("User", "cannot deactivate an admin")
    await users_repo.set_active(db, target, active=body.is_active)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin),
) -> None:
    """Permanently delete a user and all associated data."""
    if user_id == admin.id:
        raise ConflictError("User", "cannot delete yourself")
    target = await users_repo.find_by_id(db, user_id)
    if target is None:
        raise NotFoundError("User", str(user_id))
    if target.role == ROLE_ADMIN:
        raise ConflictError("User", "cannot delete an admin")
    await users_repo.hard_delete(db, target)


@router.get("/waitlist", response_model=list[WaitlistRequestOut])
async def list_waitlist(db: AsyncSession = Depends(get_db)) -> list[WaitlistRequestOut]:
    """List all pending waitlist requests, ordered by submission date."""
    return await waitlist_repo.find_pending(db)


@router.post("/waitlist/{request_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_waitlist(request_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Approve a waitlist request — sets status=approved and sends confirmation email."""
    request = await waitlist_repo.find_by_id(db, request_id)
    if request is None:
        raise NotFoundError("WaitlistRequest", str(request_id))
    await waitlist_repo.approve(db, request)
    try:
        await send_approval_email(request.email)
        await waitlist_repo.mark_email_sent(db, request)
    except Exception:
        logger.warning("Failed to send approval email to {}", request.email, exc_info=True)


@router.post("/waitlist/{request_id}/resend", status_code=status.HTTP_204_NO_CONTENT)
async def resend_waitlist(request_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Re-send the approval email for an already-approved request."""
    request = await waitlist_repo.find_by_id(db, request_id)
    if request is None:
        raise NotFoundError("WaitlistRequest", str(request_id))
    if request.status != WAITLIST_APPROVED:
        raise ConflictError("WaitlistRequest", "can only resend email for approved requests")
    await send_approval_email(request.email)
    await waitlist_repo.mark_email_sent(db, request)


@router.post("/waitlist/{request_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_waitlist(request_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Reject a waitlist request — sets status=rejected."""
    request = await waitlist_repo.find_by_id(db, request_id)
    if request is None:
        raise NotFoundError("WaitlistRequest", str(request_id))
    await waitlist_repo.reject(db, request)

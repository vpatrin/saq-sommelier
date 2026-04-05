from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import WAITLIST_APPROVED, WAITLIST_PENDING, WAITLIST_REJECTED
from core.db.models import WaitlistRequest


async def find_by_id(db: AsyncSession, request_id: int) -> WaitlistRequest | None:
    stmt = select(WaitlistRequest).where(WaitlistRequest.id == request_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_by_email(db: AsyncSession, email: str) -> WaitlistRequest | None:
    stmt = select(WaitlistRequest).where(WaitlistRequest.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(db: AsyncSession, email: str) -> WaitlistRequest | None:
    """Create a pending waitlist request. Returns None if email already exists."""
    try:
        request = WaitlistRequest(email=email)
        db.add(request)
        await db.flush()
        return request
    except IntegrityError:
        await db.rollback()
        return None


async def find_pending(db: AsyncSession) -> list[WaitlistRequest]:
    stmt = (
        select(WaitlistRequest)
        .where(WaitlistRequest.status == WAITLIST_PENDING)
        .order_by(WaitlistRequest.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def approve(db: AsyncSession, request: WaitlistRequest) -> WaitlistRequest:
    request.status = WAITLIST_APPROVED
    request.approved_at = datetime.now(UTC)
    await db.flush()
    return request


async def reject(db: AsyncSession, request: WaitlistRequest) -> WaitlistRequest:
    request.status = WAITLIST_REJECTED
    await db.flush()
    return request


async def mark_email_sent(db: AsyncSession, request: WaitlistRequest) -> WaitlistRequest:
    request.email_sent_at = datetime.now(UTC)
    await db.flush()
    return request

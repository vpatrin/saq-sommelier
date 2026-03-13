import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import InviteCode

_CODE_BYTE_LENGTH = 16


def _generate_code() -> str:
    return secrets.token_urlsafe(_CODE_BYTE_LENGTH)


async def create(db: AsyncSession, *, created_by_id: int) -> InviteCode:
    code = InviteCode(code=_generate_code(), created_by_id=created_by_id)
    db.add(code)
    await db.flush()
    return code


async def find_unused_by_code(db: AsyncSession, code: str) -> InviteCode | None:
    stmt = select(InviteCode).where(InviteCode.code == code, InviteCode.used_by_id.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def redeem(db: AsyncSession, invite: InviteCode, user_id: int) -> None:
    invite.used_by_id = user_id
    invite.used_at = datetime.now(UTC)
    await db.flush()


async def list_all(db: AsyncSession) -> list[InviteCode]:
    result = await db.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))
    return list(result.scalars().all())

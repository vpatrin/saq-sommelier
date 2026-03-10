from datetime import UTC, datetime

from core.db.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import ROLE_ADMIN


async def find_by_id(db: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_active_admin(db: AsyncSession, telegram_id: int) -> User | None:
    stmt = select(User).where(
        User.telegram_id == telegram_id, User.role == ROLE_ADMIN, User.is_active.is_(True)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession) -> list[User]:
    stmt = select(User).order_by(User.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def upsert(
    db: AsyncSession,
    telegram_id: int,
    first_name: str,
    username: str | None,
) -> User:
    """Create or update user from Telegram OAuth data. Returns the user."""
    user = await find_by_telegram_id(db, telegram_id)
    now = datetime.now(UTC)
    if user:
        user.first_name = first_name
        user.username = username
        user.last_login_at = now
    else:
        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            username=username,
            last_login_at=now,
        )
        db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def deactivate(db: AsyncSession, user_id: int) -> User | None:
    """Set is_active=False. Returns updated user, or None if not found."""
    user = await find_by_id(db, user_id)
    if user is None:
        return None
    user.is_active = False
    await db.flush()
    return user

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import ROLE_ADMIN
from core.db.models import User


async def find_by_id(db: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
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


async def upsert_telegram(
    db: AsyncSession,
    telegram_id: int,
) -> User:
    """Update last_login_at for an existing Telegram user. Returns the user."""
    user = await find_by_telegram_id(db, telegram_id)
    if user is None:
        raise ValueError(f"No user found for telegram_id={telegram_id}")
    user.last_login_at = datetime.now(UTC)
    await db.flush()
    return user


async def create_oauth_user(
    db: AsyncSession,
    *,
    email: str,
    display_name: str | None,
) -> User:
    user = User(email=email, display_name=display_name)
    db.add(user)
    await db.flush()
    return user


async def set_active(db: AsyncSession, user: User, *, active: bool) -> User:
    """Set is_active flag on an already-loaded user."""
    user.is_active = active
    await db.flush()
    return user

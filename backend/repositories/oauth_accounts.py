from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import OAuthAccount


async def find_by_provider(
    db: AsyncSession, provider: str, provider_user_id: str
) -> OAuthAccount | None:
    stmt = select(OAuthAccount).where(
        OAuthAccount.provider == provider,
        OAuthAccount.provider_user_id == provider_user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    user_id: int,
    provider: str,
    provider_user_id: str,
    email: str,
) -> OAuthAccount:
    account = OAuthAccount(
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
    )
    db.add(account)
    await db.flush()
    return account


async def list_by_user(db: AsyncSession, user_id: int) -> list[OAuthAccount]:
    stmt = (
        select(OAuthAccount)
        .where(OAuthAccount.user_id == user_id)
        .order_by(OAuthAccount.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

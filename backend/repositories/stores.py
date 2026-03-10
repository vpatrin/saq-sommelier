from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Store, UserStorePreference


async def get_all_stores(db: AsyncSession) -> list[Store]:
    """Return all stores (used for distance sorting in Python)."""
    stmt = select(Store)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_store_by_id(db: AsyncSession, saq_store_id: str) -> Store | None:
    """Return a single store by its SAQ identifier, or None."""
    stmt = select(Store).where(Store.saq_store_id == saq_store_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_stores(
    db: AsyncSession, user_id: str
) -> list[tuple[UserStorePreference, Store]]:
    """Return all store preferences for a user, with store data (INNER JOIN)."""
    stmt = (
        select(UserStorePreference, Store)
        .join(Store, UserStorePreference.saq_store_id == Store.saq_store_id)
        .where(UserStorePreference.user_id == user_id)
        .order_by(UserStorePreference.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.all())


async def add_user_store(db: AsyncSession, user_id: str, saq_store_id: str) -> UserStorePreference:
    """Insert a user store preference. Caller must handle IntegrityError for duplicates."""
    pref = UserStorePreference(user_id=user_id, saq_store_id=saq_store_id)
    db.add(pref)
    await db.flush()
    await db.refresh(pref)
    return pref


async def remove_user_store(db: AsyncSession, user_id: str, saq_store_id: str) -> bool:
    """Delete a user store preference. Returns True if deleted, False if not found."""
    stmt = delete(UserStorePreference).where(
        UserStorePreference.user_id == user_id,
        UserStorePreference.saq_store_id == saq_store_id,
    )
    result = await db.execute(stmt)
    await db.flush()
    # Return True if row existed and was deleted, False if not found
    return result.rowcount > 0

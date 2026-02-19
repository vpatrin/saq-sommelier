from collections.abc import AsyncGenerator

from core.config.settings import settings
from core.db.base import create_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

_SessionLocal = create_session_factory(settings.database_url, settings.DATABASE_ECHO)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session per request. Auto-commits on success, rolls back on error."""
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

from collections.abc import AsyncGenerator

from shared.config.settings import settings
from shared.db.base import create_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

_SessionLocal = create_session_factory(settings.database_url, settings.DATABASE_ECHO)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session per request, close it when done."""
    async with _SessionLocal() as session:
        yield session

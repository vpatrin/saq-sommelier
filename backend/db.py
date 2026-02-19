from collections.abc import AsyncGenerator

from core.config.settings import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(settings.database_url, echo=settings.DATABASE_ECHO)
_SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def verify_db_connection() -> None:
    """Check that PostgreSQL is reachable. Raises on failure."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session per request. Auto-commits on success, rolls back on error."""
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

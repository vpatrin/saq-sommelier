from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class for all SQLAlchemy models."""

    pass


def create_session_factory(
    database_url: str, echo: bool = False
) -> async_sessionmaker[AsyncSession]:
    """Create an async engine and session factory for the given database URL.

    Args:
        database_url: PostgreSQL connection string (postgresql+asyncpg://...)
        echo: Log SQL queries (useful for debugging, disable in prod)

    Returns:
        An async_sessionmaker bound to the engine.
    """
    engine = create_async_engine(database_url, echo=echo)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

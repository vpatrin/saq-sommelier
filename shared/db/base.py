"""Database configuration and session management for SAQ Sommelier.

This module provides:
- Declarative Base (parent class for all SQLAlchemy models)
- Async engine factory (creates database connections)
- Async session factory (manages transactions)

Pattern:
    In FastAPI/async apps, you create an async engine once at startup,
    then create sessions per request/operation. Each session is a
    transaction boundary (like db.session in Flask-SQLAlchemy).
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from shared.config.settings import settings

# Async engine: manages connection pool, executes SQL
# echo=True → log SQL queries (useful for debugging, disable in prod)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    future=True,  # Use SQLAlchemy 2.0 style
)

# Session factory: creates new sessions (transactions)
# expire_on_commit=False → objects remain usable after commit
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Declarative Base: parent class for all models
# Models inherit from this: class Product(Base)
Base = declarative_base()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session context manager for database transactions.

    Usage:
        async with get_async_session() as session:
            product = await session.get(Product, sku)
            await session.commit()

    The session is automatically closed after the with block.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection (test connectivity).

    Call this at application startup to verify database is reachable.
    Does NOT create tables (use Alembic migrations for that).
    """
    async with engine.begin() as conn:
        # Test connection by executing a simple query
        await conn.execute("SELECT 1")

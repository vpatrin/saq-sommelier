"""Database configuration and session management for SAQ Sommelier.

This module provides:
- Declarative Base (parent class for all SQLAlchemy models)
- Factory function to create async engine + session factory

Pattern:
    In FastAPI/async apps, you create an async engine once at startup,
    then create sessions per request/operation. Each session is a
    transaction boundary (like db.session in Flask-SQLAlchemy).

    Unlike Flask-SQLAlchemy where db = SQLAlchemy(app) creates a global,
    here we use a factory function so each service controls when/how
    the engine is created (no import-time side effects).
"""

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

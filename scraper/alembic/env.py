# ============================================================================
# SECTION 1: BOILERPLATE - Standard Alembic Setup (100% untouched)
# ============================================================================

import sys
from pathlib import Path

# Add project root to Python path so shared/ can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load scraper's .env file before importing anything that reads from environment
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ============================================================================
# SECTION 2: CUSTOM - Project-Specific Configuration
# ============================================================================
# This is the ONLY section we customized for our project.
# Everything below is what we added to make Alembic work with our setup.

# --- Custom Import 1: Base + Models (for autogenerate) ---
# Why: Alembic needs to see your SQLAlchemy models to detect schema changes
# Without this: `alembic revision --autogenerate` won't work
# Standard practice: Required for any project using autogenerate
from shared.db.base import Base
from shared.db import models  # noqa: F401 - Import models to register with Base.metadata

# --- Custom Import 2: Settings (for DATABASE_URL) ---
# Why: Don't hardcode credentials in alembic.ini, read from environment instead
# Standard practice: 12-factor apps, Docker deployments
from shared.config.settings import settings

# --- Custom Config 1: Override DATABASE_URL ---
# Why: Our app uses async SQLAlchemy (postgresql+asyncpg) for runtime,
#      but Alembic runs migrations synchronously (needs postgresql+psycopg2)
# Standard practice: Common pattern for FastAPI + async SQLAlchemy projects
database_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://",  # App runtime (async)
    "postgresql+psycopg2://",  # Alembic migrations (sync)
)
config.set_main_option("sqlalchemy.url", database_url)

# --- Custom Config 2: Set target_metadata ---
# Why: Alembic compares Base.metadata (your models) vs actual database schema
# This enables: `alembic revision --autogenerate` to detect changes
# Default value: None (autogenerate won't work)
# Standard practice: Required for autogenerate, every project does this
target_metadata = Base.metadata



# ============================================================================
# SECTION 3: BOILERPLATE - Migration Execution Logic (100% untouched)
# ============================================================================


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

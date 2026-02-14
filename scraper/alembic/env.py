# ============================================================================
# SECTION 1: IMPORTS
# ============================================================================

from logging.config import fileConfig

from shared.config.settings import settings
from shared.db import models  # noqa: F401 - Import models to register with Base.metadata
from shared.db.base import Base
from sqlalchemy import engine_from_config, pool

from alembic import context

# ============================================================================
# SECTION 2: CONFIGURATION
# ============================================================================

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override DATABASE_URL from settings instead of hardcoding in alembic.ini.
# Our app uses async SQLAlchemy (postgresql+asyncpg) for runtime,
# but Alembic runs migrations synchronously (needs postgresql+psycopg2).
database_url = settings.database_url.replace(
    "postgresql+asyncpg://",  # App runtime (async)
    "postgresql+psycopg2://",  # Alembic migrations (sync)
)
config.set_main_option("sqlalchemy.url", database_url)

# Alembic compares Base.metadata (your models) vs actual database schema.
# This enables: `alembic revision --autogenerate` to detect changes.
target_metadata = Base.metadata


# ============================================================================
# SECTION 3: MIGRATION EXECUTION LOGIC
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

# ============================================================================
# SECTION 1: IMPORTS
# ============================================================================

from logging.config import fileConfig

from alembic.operations import ops as alembic_ops
from sqlalchemy import engine_from_config, pool

from alembic import context
from core.config.settings import settings
from core.db import models  # noqa: F401 - Import models to register with Base.metadata
from core.db.base import Base

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
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Alembic compares Base.metadata (your models) vs actual database schema.
# This enables: `alembic revision --autogenerate` to detect changes.
target_metadata = Base.metadata


def _is_comment_only_alter(op: object) -> bool:
    return (
        isinstance(op, alembic_ops.AlterColumnOp)
        and op.modify_comment is not False
        and op.modify_nullable is None
        and op.modify_type is None
        and op.modify_server_default is False
        and op.modify_name is None
    )


def _strip_comment_only_alters(_context, _revision, directives):
    # Alembic has no compare_comments=False option (silently ignored in 1.x).
    # Use process_revision_directives to drop alter_column ops that only
    # change a column comment — these re-appear on every autogenerate from
    # a fresh DB because column comments aren't tracked in alembic_version.
    for script in directives:
        for upgrade_ops in (script.upgrade_ops, script.downgrade_ops):
            for migrate_ops in upgrade_ops.ops:
                if isinstance(migrate_ops, alembic_ops.ModifyTableOps):
                    migrate_ops.ops[:] = [
                        op for op in migrate_ops.ops if not _is_comment_only_alter(op)
                    ]


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
        process_revision_directives=_strip_comment_only_alters,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=_strip_comment_only_alters,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

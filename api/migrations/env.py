"""Alembic migration environment.

The database URL comes from app settings (SCHOLARSHIP_DATABASE_URL, or SQLite
in SCHOLARSHIP_DATA_DIR), so no URL or path is ever written into the repo.
Tests can override it with config.set_main_option("sqlalchemy.url", ...).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.core.config import get_database_url
from app.core.db import make_engine
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_database_url()


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (alembic upgrade --sql)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply migrations."""
    # NullPool: a migration run is short-lived, so don't keep connections open.
    engine = make_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite can't ALTER most things in place; batch mode recreates the
            # table instead. Harmless on Postgres.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

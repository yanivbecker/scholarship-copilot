"""Database engine, sessions, and the declarative Base for all models."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_database_url

# Predictable constraint names. Alembic needs names to alter or drop
# constraints later, and SQLite otherwise leaves them unnamed.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",  # all columns, e.g. user_id_key
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent class of every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    # SQLite ignores FOREIGN KEY constraints unless this is set per connection.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(url: str, **engine_options: Any) -> Engine:
    """create_engine() plus our SQLite settings. Use this, not create_engine."""
    engine = create_engine(url, **engine_options)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


@lru_cache
def get_session_factory() -> "sessionmaker[Session]":
    """Create the engine once, on first use (not at import time)."""
    return sessionmaker(make_engine(get_database_url()))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with get_session_factory()() as session:
        yield session

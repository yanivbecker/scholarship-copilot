"""Shared fixtures. Each test gets its own throwaway SQLite database, created
by running the real migrations (so tests also prove the migrations work)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.db import make_engine
from app.modules.users.models import User
from app.modules.users.service import get_or_create_owner

API_DIR = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    config = Config(toml_file=str(API_DIR / "pyproject.toml"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(name="db_url")
def fixture_db_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture(name="engine")
def fixture_engine(db_url: str) -> Iterator[Engine]:
    """An engine on a database migrated to the latest version."""
    command.upgrade(alembic_config(db_url), "head")
    engine = make_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture(name="session")
def fixture_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture(name="owner")
def fixture_owner(session: Session) -> User:
    """The single local user (test data only)."""
    user = get_or_create_owner(session)
    session.commit()
    return user

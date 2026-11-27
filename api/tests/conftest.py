"""Shared fixtures. Each test gets its own throwaway SQLite database, created
by running the real migrations (so tests also prove the migrations work)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.db import get_session, make_engine
from app.api.sources import get_fetcher
from app.core.storage import LocalFileStorage, get_storage
from app.main import create_app
from app.modules.users.models import User
from app.modules.users.service import get_or_create_owner
from tests.fake_web import FakeWeb, new_web

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


@pytest.fixture(name="storage")
def fixture_storage(tmp_path: Path) -> LocalFileStorage:
    """File storage in this test's temporary folder (never the real data dir)."""
    return LocalFileStorage(tmp_path / "files")


@pytest.fixture(name="web")
def fixture_web() -> FakeWeb:
    """A fake web (no real network). example.org exists and allows everything."""
    return new_web()


@pytest.fixture(name="client")
def fixture_client(
    engine: Engine, storage: LocalFileStorage, web: FakeWeb
) -> Iterator[TestClient]:
    """An API client using this test's throwaway database, files and fake web."""

    def test_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_fetcher] = web.fetcher
    with TestClient(app) as client:
        yield client

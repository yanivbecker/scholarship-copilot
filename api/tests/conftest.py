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

from app.ai.factory import get_ai_provider
from app.modules.background.launchd import Agent, DryRunLaunchctl
from app.modules.background.service import get_agent
from app.modules.sources.search import get_searcher
from app.core.config import get_settings
from app.core.db import get_session, make_engine
from app.api.sources import get_fetcher
from app.core.storage import LocalFileStorage, get_storage
from app.main import create_app
from app.modules.users.models import User
from app.modules.users.service import get_or_create_owner
from tests.fake_web import FakeWeb, new_web
from tests.fakes import ScriptedProvider
from tests.sample_listing import PAGE, answer, award

API_DIR = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    config = Config(toml_file=str(API_DIR / "pyproject.toml"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(autouse=True)
def no_real_keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Tests never see the owner's real API keys from api/.env: blank values
    win over the file, and a blank key means "not set"."""
    for name in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
    engine: Engine, storage: LocalFileStorage, web: FakeWeb, tmp_path: Path
) -> Iterator[TestClient]:
    """An API client using this test's throwaway database, files and fake web."""

    def test_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_fetcher] = web.fetcher
    # Never a real search service, even if api/.env has a key.
    app.dependency_overrides[get_searcher] = lambda: None
    # Never the real launchd: a dry-run agent in this test's folder.
    app.dependency_overrides[get_agent] = lambda: Agent(
        tmp_path / "LaunchAgents",
        DryRunLaunchctl(),
        tmp_path / "data",
        find_uv=lambda: "/opt/fake/bin/uv",
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture(name="scholarship_id")
def fixture_scholarship_id(client: TestClient) -> int:
    """The fictional sample award, extracted through the API with a scripted AI."""
    provider = ScriptedProvider(answer(award()))
    client.app.dependency_overrides[get_ai_provider] = lambda: provider  # type: ignore[attr-defined]
    source = client.post(
        "/api/v1/sources", json={"url": "https://example.org/awards"}
    ).json()
    client.post(f"/api/v1/sources/{source['id']}/paste", json={"text": PAGE})
    client.post(f"/api/v1/sources/{source['id']}/extract")
    [scholarship] = client.get("/api/v1/scholarships").json()
    return int(scholarship["id"])

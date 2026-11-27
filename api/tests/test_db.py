"""Database + migration tests. Each test gets its own throwaway SQLite file."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.orm import Session

from app.core.db import make_engine
from app.modules.users.models import User

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


def test_upgrade_creates_users_table(engine: Engine) -> None:
    assert "users" in inspect(engine).get_table_names()


def test_user_round_trip_sets_created_at(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(User(display_name="Demo User"))  # demo data, test-only
        session.commit()

        user = session.scalars(select(User)).one()

    assert user.display_name == "Demo User"
    assert user.created_at is not None


def test_sqlite_foreign_keys_are_enforced(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_downgrade_to_base_removes_tables(db_url: str, engine: Engine) -> None:
    command.downgrade(alembic_config(db_url), "base")

    assert "users" not in inspect(engine).get_table_names()


def test_models_match_migrations(db_url: str, engine: Engine) -> None:
    # Fails if someone changed a model but forgot to generate a migration.
    assert engine is not None  # ensures the DB is migrated first
    command.check(alembic_config(db_url))

"""Database + migration tests. Each test gets its own throwaway SQLite file."""

from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.modules.users.models import User
from tests.conftest import alembic_config


def test_upgrade_creates_all_tables(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    assert {"users", "profiles", "profile_facts", "stories"} <= tables


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

    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}


def test_models_match_migrations(db_url: str, engine: Engine) -> None:
    # Fails if someone changed a model but forgot to generate a migration.
    assert engine is not None  # ensures the DB is migrated first
    command.check(alembic_config(db_url))

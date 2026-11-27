"""UTCDateTime: timestamps come back timezone-aware, in UTC, on SQLite too."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.core.types import UTCDateTime
from app.modules.users.service import get_or_create_owner

metadata = MetaData()
events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("at", UTCDateTime()),
)


@pytest.fixture(name="table_engine")
def fixture_table_engine(engine: Engine) -> Engine:
    metadata.create_all(engine)
    return engine


def round_trip(engine: Engine, value: datetime | None) -> datetime | None:
    with engine.begin() as conn:
        conn.execute(insert(events).values(at=value))
        result: datetime | None = conn.execute(select(events.c.at)).scalar_one()
    return result


def test_utc_value_comes_back_aware(table_engine: Engine) -> None:
    value = datetime(2027, 3, 1, 9, 30, tzinfo=UTC)

    result = round_trip(table_engine, value)

    assert result == value
    assert result is not None and result.tzinfo is UTC


def test_other_zones_are_converted_to_utc(table_engine: Engine) -> None:
    new_york = timezone(timedelta(hours=-5))

    result = round_trip(table_engine, datetime(2027, 3, 1, 9, 0, tzinfo=new_york))

    assert result == datetime(2027, 3, 1, 14, 0, tzinfo=UTC)


def test_naive_datetimes_are_refused(table_engine: Engine) -> None:
    with pytest.raises(StatementError, match="timezone-aware"):
        round_trip(table_engine, datetime(2027, 3, 1, 9, 0))


def test_none_is_allowed(table_engine: Engine) -> None:
    assert round_trip(table_engine, None) is None


def test_server_default_timestamps_are_aware(session: Session) -> None:
    # created_at comes from the database's CURRENT_TIMESTAMP (UTC).
    owner = get_or_create_owner(session)
    session.commit()
    session.refresh(owner)

    assert owner.created_at.tzinfo is UTC

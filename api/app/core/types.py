"""Custom column types.

UTCDateTime: SQLite has no time zones, so a plain DateTime(timezone=True)
comes back "naive" (no offset), and 09:00 could mean any zone. This type
stores every timestamp as UTC and always returns it marked as UTC, on SQLite
and Postgres alike. Deadlines (Phase 6) depend on this.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from alembic.autogenerate.api import AutogenContext

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(  # pylint: disable=abstract-method,too-many-ancestors
    TypeDecorator[datetime]
):
    """A timezone-aware datetime, stored and returned in UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime needs a timezone-aware datetime")
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        # SQLite returns naive values; they were stored as UTC.
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def alembic_render_item(
    type_: str, obj: Any, _context: AutogenContext
) -> str | Literal[False]:
    """Alembic hook: write app column types as plain SQLAlchemy types.

    Migrations must keep working forever, so they shouldn't import app code
    that may change. In the database, UTCDateTime is just DateTime(timezone).
    """
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False  # Alembic's default rendering for everything else

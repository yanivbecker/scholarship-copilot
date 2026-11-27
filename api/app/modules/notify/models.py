"""In-app notifications (FR-N5) and what was last notified (FR-N4).

`WatchState` keeps, per scholarship, the material facts the student was last
told about (deadline, amount, eligibility, requirements). The daily job
compares against it, so the same news is never announced twice.
`Notification.dedup_key` is unique per user as a second guard: the same
event can't be inserted twice even if two runs overlap.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import UTCDateTime


class NotificationKind(StrEnum):
    """What a notification is about (each can be switched off, FR-N5)."""

    NEW_MATCH = "new_match"  # a new scholarship you may be eligible for
    CHANGED = "changed"  # deadline, amount, eligibility or requirements changed
    DEADLINE = "deadline"  # a deadline is 14 or 3 days away


def _user_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Notification(Base):  # pylint: disable=too-many-instance-attributes
    """One message on the Today screen."""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedup_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    scholarship_id: Mapped[int | None] = mapped_column(
        ForeignKey("scholarships.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(
            NotificationKind,
            native_enum=False,
            length=20,
            values_callable=lambda members: [m.value for m in members],
        )
    )
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    dedup_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class WatchState(Base):
    """The material facts of a scholarship as last notified."""

    __tablename__ = "watch_states"
    __table_args__ = (UniqueConstraint("user_id", "scholarship_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    scholarship_id: Mapped[int] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())

"""Profile tables: settings per user, typed facts, and the story bank.

Every row has a user_id with ON DELETE CASCADE, so deleting a user deletes
all of their personal data (NFR-8, NFR-12).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import true as sa_true  # SQL TRUE, portable to Postgres
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import UTCDateTime
from app.modules.profile.catalog import FactValue


class OperatingMode(StrEnum):
    """FR-P7. Hybrid is the flagship mode."""

    DISCOVERY = "discovery"
    HYBRID = "hybrid"
    AUTOMATION = "automation"


class FactOrigin(StrEnum):
    """Where a fact's current value came from (FR-P3)."""

    QUESTIONNAIRE = "questionnaire"  # onboarding wizard
    RESUME = "resume"  # confirmed from a resume import
    SCHOLARSHIP_ANSWER = "scholarship_answer"  # answered for one scholarship
    MANUAL = "manual"  # typed or edited in the profile editor


def _str_enum(enum_class: type[StrEnum]) -> Enum:
    # Store the lowercase values ("hybrid"), not the Python names ("HYBRID"),
    # as plain strings so SQLite and Postgres behave the same.
    return Enum(
        enum_class,
        native_enum=False,
        length=32,
        values_callable=lambda members: [m.value for m in members],
    )


def _user_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class _Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )


class Profile(_Timestamps, Base):
    """One per user: preferences and onboarding progress."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    operating_mode: Mapped[OperatingMode] = mapped_column(
        _str_enum(OperatingMode), default=OperatingMode.HYBRID
    )
    # In-app notifications only in v1 (FR-N5). Used from Phase 8.
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=sa_true()
    )
    # Last wizard step the student finished; None until they start (FR-P1).
    onboarding_step: Mapped[str | None] = mapped_column(String(50))
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ProfileFact(_Timestamps, Base):
    """One typed fact about the student, e.g. key="gpa", value=3.8.

    Catalog facts use their catalog key. Scholarship-specific answers use
    "custom.<slug>" keys and keep the original question as `label`.
    """

    __tablename__ = "profile_facts"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str | None] = mapped_column(String(200))  # custom facts only
    value: Mapped[FactValue] = mapped_column(JSON)
    origin: Mapped[FactOrigin] = mapped_column(_str_enum(FactOrigin))
    # Extra context about the origin, e.g. the resume file name.
    origin_detail: Mapped[str | None] = mapped_column(String(500))


class Story(_Timestamps, Base):
    """An experience in the student's own words (FR-P5).

    `body` is stored exactly as written. It is the only source material
    writing help may draw on, so it must never be rewritten by the app.
    """

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    themes: Mapped[list[str]] = mapped_column(JSON, default=list)

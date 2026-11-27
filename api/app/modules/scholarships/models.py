"""Scholarships, their yearly cycles, and evidence-backed criteria.

A scholarship (e.g. "Test Foundation Award") recurs every year; each year is
a cycle with its own amount, deadline and criteria (FR-D8). Every criterion
keeps the verbatim quote it came from and the source URL (FR-D5).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.types import UTCDateTime


def _user_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Scholarship(Base):
    """A scholarship program, independent of any one year."""

    __tablename__ = "scholarships"
    __table_args__ = (UniqueConstraint("user_id", "match_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    name: Mapped[str] = mapped_column(String(300))
    sponsor: Mapped[str | None] = mapped_column(String(300))
    official_url: Mapped[str | None] = mapped_column(String(2000))
    description: Mapped[str | None] = mapped_column(Text)
    # Normalized "name|sponsor": exact-match identity. Fuzzy dedup is 5.5.
    match_key: Mapped[str] = mapped_column(String(620))
    # Tracking status (FR-UI4); the state machine arrives in Phase 6.
    status: Mapped[str] = mapped_column(String(40), default="discovered")
    # [{"signal": ..., "evidence": ...}] (FR-D9): shown, never used to hide.
    scam_flags: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    cycles: Mapped[list["ScholarshipCycle"]] = relationship(
        back_populates="scholarship",
        cascade="all, delete-orphan",
        order_by="ScholarshipCycle.year.desc()",
    )


class ScholarshipCycle(Base):  # pylint: disable=too-many-instance-attributes
    """One year of a scholarship: amount, deadline and criteria (FR-D8)."""

    __tablename__ = "scholarship_cycles"
    __table_args__ = (UniqueConstraint("scholarship_id", "year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = _user_fk()
    year: Mapped[int] = mapped_column(Integer)
    # Amount exactly as the sponsor wrote it, plus parsed numbers if clear.
    amount_text: Mapped[str | None] = mapped_column(String(300))
    amount_min: Mapped[int | None] = mapped_column(Integer)
    amount_max: Mapped[int | None] = mapped_column(Integer)
    deadline: Mapped[date | None] = mapped_column(Date)
    deadline_quote: Mapped[str | None] = mapped_column(String(500))
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    source_url: Mapped[str] = mapped_column(String(2000))
    extracted_by: Mapped[str] = mapped_column(String(100))  # model name or "manual"
    extracted_at: Mapped[datetime] = mapped_column(UTCDateTime())

    scholarship: Mapped[Scholarship] = relationship(back_populates="cycles")
    criteria: Mapped[list["Criterion"]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        order_by="Criterion.position",
    )


class Criterion(Base):
    """One eligibility requirement, with the exact words it came from."""

    __tablename__ = "criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("scholarship_cycles.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = _user_fk()
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))  # a CriterionKind value
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    quote: Mapped[str] = mapped_column(Text)  # verbatim from the source
    source_url: Mapped[str] = mapped_column(String(2000))

    cycle: Mapped[ScholarshipCycle] = relationship(back_populates="criteria")

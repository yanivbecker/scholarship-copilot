"""Scholarship sources: web pages the student has approved for discovery.

Phase 4 only stores them (onboarding "first sources"). Phase 5 adds fetching,
snapshots, and candidates suggested by web search (FR-D1).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SourceStatus(StrEnum):
    """Added by hand = approved. Search suggestions start as pending (Phase 5)."""

    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


class Source(Base):
    """One web page to check for scholarships."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("user_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(2000))  # normalized, see url_safety
    label: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[SourceStatus] = mapped_column(
        Enum(
            SourceStatus,
            native_enum=False,
            length=32,
            values_callable=lambda members: [m.value for m in members],
        ),
        default=SourceStatus.APPROVED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

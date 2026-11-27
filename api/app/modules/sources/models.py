"""Scholarship sources: web pages the student has approved for discovery.

Phase 4 only stores them (onboarding "first sources"). Phase 5 adds fetching,
snapshots, and candidates suggested by web search (FR-D1).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import UTCDateTime


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
        UTCDateTime(), server_default=func.now()
    )

    # Result of the most recent check (a FetchStatus value, or "pasted").
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_result: Mapped[str | None] = mapped_column(String(32))
    last_message: Mapped[str | None] = mapped_column(String(500))
    # When the page's text last changed (FR-D7).
    last_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # HTTP validators for conditional requests (FR-D2 "HTTP caching").
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(100))


class SnapshotOrigin(StrEnum):
    """How a snapshot's text was obtained."""

    FETCHED = "fetched"
    PASTED = "pasted"  # FR-D4: login-only portals are pasted, never crawled


class PageSnapshot(Base):
    """The readable text of a source at one point in time.

    Extraction (5.3) only runs on snapshots whose text changed (FR-D7).
    """

    __tablename__ = "page_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    origin: Mapped[SnapshotOrigin] = mapped_column(
        Enum(
            SnapshotOrigin,
            native_enum=False,
            length=16,
            values_callable=lambda members: [m.value for m in members],
        )
    )
    url: Mapped[str] = mapped_column(String(2000))  # final URL after redirects
    content_type: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    changed: Mapped[bool] = mapped_column(Boolean)  # differs from the previous one
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())

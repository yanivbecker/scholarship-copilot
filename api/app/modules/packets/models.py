"""Application packets (Phase 7): what one application needs, and the
student's responses.

* Packet: one per scholarship cycle. Holds the AI-use rules check (FR-A1/A2)
  and the student's final approval (FR-A7).
* PacketItem: one thing to prepare: an essay, a short answer, a document
  (transcript, recommendation) or a form field (FR-A6).
* ResponseVersion: every saved version of a response, never overwritten
  (FR-A8). A version is "approved" only by an explicit student action.
* LibraryEntry: approved responses kept for reuse in later applications.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
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


class RulesStatus(StrEnum):
    """The scholarship's policy on AI help (FR-A1). Unclear counts as no."""

    UNCHECKED = "unchecked"
    ALLOWED = "allowed"
    PROHIBITED = "prohibited"
    UNCLEAR = "unclear"


class ItemKind(StrEnum):
    """What kind of thing the item is."""

    ESSAY = "essay"
    SHORT_ANSWER = "short_answer"
    DOCUMENT = "document"  # transcript, recommendation letter, resume, ...
    FORM_FIELD = "form_field"  # a field to fill in on the application form


class LimitUnit(StrEnum):
    """How a length limit is counted."""

    CHARS = "chars"
    WORDS = "words"


class VersionOrigin(StrEnum):
    """Who produced a version's text."""

    STUDENT = "student"  # typed by the student
    AI_DRAFT = "ai_draft"  # drafted from profile facts + stories (FR-A4)
    LIBRARY = "library"  # copied from a previously approved response


def _str_enum(enum_class: type[StrEnum], length: int = 20) -> Enum:
    return Enum(
        enum_class,
        native_enum=False,
        length=length,
        values_callable=lambda members: [m.value for m in members],
    )


def _user_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Packet(Base):  # pylint: disable=too-many-instance-attributes
    """Everything for one scholarship application (one cycle)."""

    __tablename__ = "packets"
    __table_args__ = (UniqueConstraint("cycle_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    scholarship_id: Mapped[int] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), index=True
    )
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("scholarship_cycles.id", ondelete="CASCADE")
    )
    rules_status: Mapped[RulesStatus] = mapped_column(
        _str_enum(RulesStatus), default=RulesStatus.UNCHECKED
    )
    rules_quote: Mapped[str | None] = mapped_column(Text)  # verbatim (FR-A1)
    rules_source_url: Mapped[str | None] = mapped_column(String(2000))
    rules_confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

    items: Mapped[list["PacketItem"]] = relationship(
        back_populates="packet",
        cascade="all, delete-orphan",
        order_by="PacketItem.position",
    )


class PacketItem(Base):  # pylint: disable=too-many-instance-attributes
    """One thing the application asks for."""

    __tablename__ = "packet_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    packet_id: Mapped[int] = mapped_column(
        ForeignKey("packets.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = _user_fk()
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[ItemKind] = mapped_column(_str_enum(ItemKind))
    title: Mapped[str] = mapped_column(String(300))
    # The prompt exactly as the sponsor wrote it, or the student's own note.
    prompt: Mapped[str | None] = mapped_column(Text)
    prompt_source_url: Mapped[str | None] = mapped_column(String(2000))
    limit_value: Mapped[int | None] = mapped_column(Integer)
    limit_unit: Mapped[LimitUnit | None] = mapped_column(_str_enum(LimitUnit))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    # Documents and form fields are ticked off; writing items get approved.
    done: Mapped[bool] = mapped_column(Boolean, default=False)

    packet: Mapped[Packet] = relationship(back_populates="items")
    versions: Mapped[list["ResponseVersion"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ResponseVersion.number",
    )


class ResponseVersion(Base):  # pylint: disable=too-many-instance-attributes
    """One saved version of a response. Versions are never edited (FR-A8)."""

    __tablename__ = "response_versions"
    __table_args__ = (UniqueConstraint("item_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("packet_items.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = _user_fk()
    number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    origin: Mapped[VersionOrigin] = mapped_column(_str_enum(VersionOrigin))
    # For AI drafts: which facts / stories each sentence came from (FR-A5).
    provenance: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    item: Mapped[PacketItem] = relationship(back_populates="versions")


class LibraryEntry(Base):
    """An approved response kept for reuse (FR-A8)."""

    __tablename__ = "library_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk()
    title: Mapped[str] = mapped_column(String(300))
    prompt: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    scholarship_name: Mapped[str] = mapped_column(String(300))
    source_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("response_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

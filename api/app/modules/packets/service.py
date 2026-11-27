"""Packets, items, versioned responses and the reuse library (FR-A6, FR-A8).

Rules that matter here:
* A response version is never edited; saving creates a new version (FR-A8).
* Approval is an explicit student action, recorded in the audit log (FR-A7).
* Length limits are checked and reported, so copy-ready text fits the form
  (FR-A6). An over-limit version can be saved but not approved.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.eligibility.service import current_cycle
from app.modules.packets.models import (
    ItemKind,
    LibraryEntry,
    LimitUnit,
    Packet,
    PacketItem,
    ResponseVersion,
    VersionOrigin,
)
from app.modules.scholarships import service as scholarships
from app.modules.tracking.models import AuditEvent

MAX_TITLE = 300
MAX_PROMPT = 5000
MAX_RESPONSE = 50_000
WRITING_KINDS = frozenset({ItemKind.ESSAY, ItemKind.SHORT_ANSWER})

VERSION_APPROVED = "response_approved"
PACKET_APPROVED = "packet_approved"
PACKET_APPROVAL_WITHDRAWN = "packet_approval_withdrawn"


class PacketError(ValueError):
    """The request can't be done. The message is user-facing."""


class PacketNotFoundError(LookupError):
    """No such packet, item or version for this user."""


# --- Length limits (FR-A6) --------------------------------------------------


@dataclass(frozen=True)
class LengthCheck:
    """How long a text is, against the item's limit (if any)."""

    chars: int
    words: int
    limit_value: int | None
    limit_unit: LimitUnit | None

    @property
    def used(self) -> int:
        return self.words if self.limit_unit is LimitUnit.WORDS else self.chars

    @property
    def over_limit(self) -> bool:
        return self.limit_value is not None and self.used > self.limit_value


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def check_length(item: PacketItem, text: str) -> LengthCheck:
    return LengthCheck(len(text), count_words(text), item.limit_value, item.limit_unit)


# --- Packets ------------------------------------------------------------------


def get_or_create_packet(
    session: Session, user_id: int, scholarship_id: int, today: date
) -> Packet:
    """The packet for the scholarship's current cycle (created on first use)."""
    scholarship = scholarships.get_scholarship(session, user_id, scholarship_id)
    cycle = current_cycle(scholarship, today)
    if cycle is None:
        raise PacketError("This scholarship has no cycle to apply to yet.")
    packet = session.scalars(
        select(Packet)
        .where(Packet.cycle_id == cycle.id, Packet.user_id == user_id)
        .options(selectinload(Packet.items).selectinload(PacketItem.versions))
    ).first()
    if packet is None:
        packet = Packet(
            user_id=user_id, scholarship_id=scholarship.id, cycle_id=cycle.id
        )
        session.add(packet)
        session.flush()
    return packet


def get_packet(session: Session, user_id: int, packet_id: int) -> Packet:
    packet = session.scalars(
        select(Packet)
        .where(Packet.id == packet_id, Packet.user_id == user_id)
        .options(selectinload(Packet.items).selectinload(PacketItem.versions))
    ).first()
    if packet is None:
        raise PacketNotFoundError(f"No packet {packet_id}")
    return packet


def get_item(session: Session, user_id: int, item_id: int) -> PacketItem:
    item = session.scalars(
        select(PacketItem).where(
            PacketItem.id == item_id, PacketItem.user_id == user_id
        )
    ).first()
    if item is None:
        raise PacketNotFoundError(f"No item {item_id}")
    return item


# --- Items ----------------------------------------------------------------------


@dataclass(frozen=True)
class ItemFields:
    """What the student (or a verified suggestion) says an item is."""

    kind: ItemKind
    title: str
    prompt: str | None = None
    prompt_source_url: str | None = None
    limit_value: int | None = None
    limit_unit: LimitUnit | None = None
    required: bool = True


def _clean_item(fields: ItemFields) -> ItemFields:
    title = " ".join(fields.title.split())
    if not title or len(title) > MAX_TITLE:
        raise PacketError(f"Give the item a title (up to {MAX_TITLE} characters).")
    prompt = (fields.prompt or "").strip() or None
    if prompt and len(prompt) > MAX_PROMPT:
        raise PacketError(f"The prompt must be at most {MAX_PROMPT} characters.")
    if (fields.limit_value is None) != (fields.limit_unit is None):
        raise PacketError("A length limit needs both a number and a unit.")
    if fields.limit_value is not None and not 1 <= fields.limit_value <= 100_000:
        raise PacketError("The length limit must be between 1 and 100,000.")
    return ItemFields(
        fields.kind,
        title,
        prompt,
        fields.prompt_source_url,
        fields.limit_value,
        fields.limit_unit,
        fields.required,
    )


def add_item(session: Session, packet: Packet, fields: ItemFields) -> PacketItem:
    clean = _clean_item(fields)
    position = len(packet.items)
    item = PacketItem(
        packet_id=packet.id,
        user_id=packet.user_id,
        position=position,
        kind=clean.kind,
        title=clean.title,
        prompt=clean.prompt,
        prompt_source_url=clean.prompt_source_url,
        limit_value=clean.limit_value,
        limit_unit=clean.limit_unit,
        required=clean.required,
    )
    packet.items.append(item)
    session.flush()
    return item


def update_item(
    session: Session, item: PacketItem, fields: ItemFields, *, done: bool | None
) -> PacketItem:
    clean = _clean_item(fields)
    item.kind = clean.kind
    item.title = clean.title
    item.prompt = clean.prompt
    item.limit_value = clean.limit_value
    item.limit_unit = clean.limit_unit
    item.required = clean.required
    if done is not None:
        if done and item.kind in WRITING_KINDS:
            raise PacketError("Writing items are finished by approving a response.")
        item.done = done
    session.flush()
    return item


def delete_item(session: Session, item: PacketItem) -> None:
    session.delete(item)
    session.flush()


# --- Versions and approval ------------------------------------------------------


def latest_version(item: PacketItem) -> ResponseVersion | None:
    return item.versions[-1] if item.versions else None


def approved_version(item: PacketItem) -> ResponseVersion | None:
    approved = [v for v in item.versions if v.approved_at is not None]
    return approved[-1] if approved else None


def save_version(  # pylint: disable=too-many-arguments
    session: Session,
    item: PacketItem,
    text: str,
    *,
    origin: VersionOrigin = VersionOrigin.STUDENT,
    provenance: list[dict[str, object]] | None = None,
) -> ResponseVersion:
    """Add a new version. Earlier versions stay exactly as they were."""
    if item.kind not in WRITING_KINDS:
        raise PacketError("Only essays and short answers have written responses.")
    if not text.strip():
        raise PacketError("Write something before saving.")
    if len(text) > MAX_RESPONSE:
        raise PacketError(f"Responses can be at most {MAX_RESPONSE:,} characters.")
    number = (
        session.scalar(
            select(func.max(ResponseVersion.number)).where(
                ResponseVersion.item_id == item.id
            )
        )
        or 0
    ) + 1
    version = ResponseVersion(
        item_id=item.id,
        user_id=item.user_id,
        number=number,
        text=text,
        origin=origin,
        provenance=provenance,
    )
    item.versions.append(version)
    session.flush()
    return version


def approve_version(
    session: Session, item: PacketItem, version_id: int, *, now: datetime | None = None
) -> ResponseVersion:
    """The student approves this exact text (FR-A7). Added to the library."""
    version = next((v for v in item.versions if v.id == version_id), None)
    if version is None:
        raise PacketNotFoundError(f"No version {version_id}")
    if check_length(item, version.text).over_limit:
        raise PacketError(
            "This version is longer than the limit. Shorten it before approving."
        )
    now = now or datetime.now(UTC)
    version.approved_at = now
    packet = item.packet
    scholarship = scholarships.get_scholarship(
        session, item.user_id, packet.scholarship_id
    )
    session.add(
        LibraryEntry(
            user_id=item.user_id,
            title=item.title,
            prompt=item.prompt,
            text=version.text,
            scholarship_name=scholarship.name,
            source_version_id=version.id,
        )
    )
    _audit(
        session,
        packet,
        name=scholarship.name,
        action=VERSION_APPROVED,
        note=f"{item.title} (v{version.number})",
        now=now,
    )
    # Changing what's approved means the packet needs approving again.
    packet.approved_at = None
    session.flush()
    return version


def list_library(session: Session, user_id: int) -> list[LibraryEntry]:
    return list(
        session.scalars(
            select(LibraryEntry)
            .where(LibraryEntry.user_id == user_id)
            .order_by(LibraryEntry.created_at.desc(), LibraryEntry.id.desc())
        )
    )


def use_library_entry(
    session: Session, item: PacketItem, entry_id: int
) -> ResponseVersion:
    """Start from a previously approved response (a new, unapproved version)."""
    entry = session.scalars(
        select(LibraryEntry).where(
            LibraryEntry.id == entry_id, LibraryEntry.user_id == item.user_id
        )
    ).first()
    if entry is None:
        raise PacketNotFoundError(f"No library entry {entry_id}")
    return save_version(session, item, entry.text, origin=VersionOrigin.LIBRARY)


# --- Packet completeness and approval (FR-A7) ---------------------------------


@dataclass(frozen=True)
class Progress:
    """How far the packet is: required items finished, and what's missing."""

    finished: int
    required: int
    missing: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return self.finished == self.required


def item_finished(item: PacketItem) -> bool:
    if item.kind in WRITING_KINDS:
        return approved_version(item) is not None
    return item.done


def progress(packet: Packet) -> Progress:
    required = [i for i in packet.items if i.required]
    missing = tuple(i.title for i in required if not item_finished(i))
    return Progress(len(required) - len(missing), len(required), missing)


def approve_packet(
    session: Session, packet: Packet, *, now: datetime | None = None
) -> Packet:
    """The student approves the whole packet as ready to submit."""
    if not packet.items:
        raise PacketError("Add the application's items before approving the packet.")
    state = progress(packet)
    if not state.complete:
        raise PacketError(
            "Finish every required item first: " + ", ".join(state.missing) + "."
        )
    now = now or datetime.now(UTC)
    packet.approved_at = now
    name = scholarships.get_scholarship(
        session, packet.user_id, packet.scholarship_id
    ).name
    _audit(
        session,
        packet,
        name=name,
        action=PACKET_APPROVED,
        note=None,
        now=now,
    )
    session.flush()
    return packet


def withdraw_packet_approval(session: Session, packet: Packet) -> Packet:
    if packet.approved_at is not None:
        packet.approved_at = None
        name = scholarships.get_scholarship(
            session, packet.user_id, packet.scholarship_id
        ).name
        _audit(
            session,
            packet,
            name=name,
            action=PACKET_APPROVAL_WITHDRAWN,
            note=None,
            now=datetime.now(
                UTC,
            ),
        )
        session.flush()
    return packet


def _audit(  # pylint: disable=too-many-arguments
    session: Session,
    packet: Packet,
    *,
    name: str,
    action: str,
    note: str | None,
    now: datetime,
) -> None:
    session.add(
        AuditEvent(
            user_id=packet.user_id,
            scholarship_id=packet.scholarship_id,
            scholarship_name=name,
            action=action,
            note=note[:500] if note else None,
            created_at=now,
        )
    )

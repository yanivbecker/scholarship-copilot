"""What the browser extension may fill (FR-X1), and the record of each fill.

The extension only ever receives a packet's *fill sheet*: the exact text the
student approved for each item, and only once the whole packet is approved.
Nothing comes straight from the profile: "Add common fields" copies profile
facts into ordinary form-field items, which the student still approves one
by one like any other answer.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.packets.models import (
    ItemKind,
    Packet,
    PacketItem,
    VersionOrigin,
)
from app.modules.packets.provenance import fact_parts
from app.modules.packets.service import (
    RESPONSE_KINDS,
    ItemFields,
    PacketError,
    add_item,
    approved_version,
    save_version,
)
from app.modules.profile import repository as profile_repo
from app.modules.scholarships import service as scholarships
from app.modules.scholarships.models import Scholarship, ScholarshipCycle
from app.modules.tracking.models import AuditEvent

AUTOFILL_USED = "autofill_used"

# Fields most application forms ask for, in form order. Identity and study
# facts only: sensitive facts (citizenship, finances, demographics) are left
# for the student to add deliberately, as a custom item, if a form needs them.
COMMON_FIELDS = (
    ("full_name", "Full name"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("date_of_birth", "Date of birth"),
    ("city", "City"),
    ("state_of_residence", "State"),
    ("school_name", "School"),
    ("major", "Major"),
    ("gpa", "GPA"),
    ("expected_graduation_year", "Expected graduation year"),
)


def add_common_fields(session: Session, packet: Packet) -> list[PacketItem]:
    """Add a form-field item for each common fact the profile has, with the
    fact's value as an *unapproved* first version. Skips titles already there."""
    facts = {f.key: f for f in profile_repo.list_facts(session, packet.user_id)}
    existing = {i.title.casefold() for i in packet.items}
    added = []
    for key, title in COMMON_FIELDS:
        fact = facts.get(key)
        if fact is None or title.casefold() in existing:
            continue
        item = add_item(session, packet, ItemFields(ItemKind.FORM_FIELD, title))
        save_version(session, item, fact_parts(fact)[1], origin=VersionOrigin.PROFILE)
        added.append(item)
    return added


@dataclass(frozen=True)
class FillEntry:
    """One approved answer, and what the extension uses to find its field."""

    item_id: int
    kind: ItemKind
    title: str
    prompt: str | None
    text: str


@dataclass(frozen=True)
class FillSheet:
    """Everything the extension may type into one application."""

    packet_id: int
    scholarship_name: str
    official_url: str | None
    entries: tuple[FillEntry, ...]


def fill_sheet(session: Session, packet: Packet) -> FillSheet:
    """FR-X1: only an approved packet, only approved versions."""
    if packet.approved_at is None:
        raise PacketError(
            "Approve the packet first: the extension only fills approved answers."
        )
    scholarship = scholarships.get_scholarship(
        session, packet.user_id, packet.scholarship_id
    )
    entries = []
    for item in packet.items:
        version = approved_version(item) if item.kind in RESPONSE_KINDS else None
        if version is not None:
            entries.append(
                FillEntry(item.id, item.kind, item.title, item.prompt, version.text)
            )
    return FillSheet(
        packet.id, scholarship.name, scholarship.official_url, tuple(entries)
    )


@dataclass(frozen=True)
class ApprovedPacket:
    """A packet the extension can offer, with the site it belongs to."""

    packet_id: int
    scholarship_id: int
    name: str
    hosts: tuple[str, ...]
    approved_at: datetime


def _host(url: str | None) -> str | None:
    host = urlsplit(url).hostname if url else None
    return host.removeprefix("www.") if host else None


def approved_packets(session: Session, user_id: int) -> list[ApprovedPacket]:
    packets = session.scalars(
        select(Packet)
        .where(Packet.user_id == user_id, Packet.approved_at.is_not(None))
        .order_by(Packet.approved_at.desc())
    )
    out = []
    for packet in packets:
        scholarship = session.get(Scholarship, packet.scholarship_id)
        cycle = session.get(ScholarshipCycle, packet.cycle_id)
        if scholarship is None or packet.approved_at is None:
            continue
        urls = (scholarship.official_url, cycle.source_url if cycle else None)
        hosts = {h for h in (_host(u) for u in urls) if h}
        out.append(
            ApprovedPacket(
                packet.id,
                scholarship.id,
                scholarship.name,
                tuple(sorted(hosts)),
                packet.approved_at,
            )
        )
    return out


def record_fill(  # pylint: disable=too-many-arguments
    session: Session,
    packet: Packet,
    *,
    host: str,
    filled: int,
    unmatched: int,
    now: datetime | None = None,
) -> None:
    """FR-A7: the audit log says when the extension filled what, and where.
    Only counts and the site's host name are kept, never the page's content."""
    name = scholarships.get_scholarship(
        session, packet.user_id, packet.scholarship_id
    ).name
    session.add(
        AuditEvent(
            user_id=packet.user_id,
            scholarship_id=packet.scholarship_id,
            scholarship_name=name,
            action=AUTOFILL_USED,
            note=(
                f"Filled {filled} field(s) on {host[:200]}; "
                f"{unmatched} left for you to fill"
            ),
            created_at=now or datetime.now(UTC),
        )
    )
    session.flush()

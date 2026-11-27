"""Changing a scholarship's status, with the system's checks (FR-UI4, FR-A7)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.eligibility import service as eligibility
from app.modules.eligibility.engine import Verdict
from app.modules.packets import service as packets
from app.modules.scholarships import service as scholarships
from app.modules.scholarships.models import Scholarship
from app.modules.tracking.models import AuditEvent
from app.modules.tracking.status import LABELS, TRANSITIONS, ApplicationStatus

STATUS_CHANGED = "status_changed"
MAX_NOTE = 500


class StatusChangeError(ValueError):
    """The change isn't allowed right now. The message is user-facing."""


@dataclass(frozen=True)
class NextStep:
    """A status the scholarship could move to, and why not if it can't yet."""

    status: ApplicationStatus
    label: str
    blocked_reason: str | None = None
    needs_confirmation: bool = False


def current_status(scholarship: Scholarship) -> ApplicationStatus:
    try:
        return ApplicationStatus(scholarship.status)
    except ValueError:
        return ApplicationStatus.DISCOVERED  # unknown legacy value: start over


def _blocked_reason(
    session: Session, scholarship: Scholarship, target: ApplicationStatus, today: date
) -> str | None:
    """The system's own checks, beyond the allowed-transitions table."""
    if target is ApplicationStatus.ELIGIBILITY_CONFIRMED:
        verdict = eligibility.eligibility_for(
            session, scholarship.user_id, scholarship.id, today
        ).result.verdict
        if verdict is not Verdict.ELIGIBLE:
            return (
                "Eligibility can only be confirmed when every listed requirement "
                "is met. Answer the open questions first."
            )
    current = current_status(scholarship)
    if (
        target is ApplicationStatus.AWAITING_APPROVAL
        and current is ApplicationStatus.IN_PROGRESS
    ):
        return _packet_incomplete(session, scholarship, today)
    if (
        target is ApplicationStatus.SUBMITTED
        and current is ApplicationStatus.AWAITING_APPROVAL
    ):
        packet = packets.find_current_packet(session, scholarship, today)
        if packet is None or packet.approved_at is None:
            return "Approve the application packet before marking it submitted."
    return None


def _packet_incomplete(
    session: Session, scholarship: Scholarship, today: date
) -> str | None:
    """FR-A7: approval waits until every required item is finished."""
    packet = packets.find_current_packet(session, scholarship, today)
    if packet is None or not packet.items:
        return "Add the application's items to its packet first."
    state = packets.progress(packet)
    if not state.complete:
        return "Finish every required item first: " + ", ".join(state.missing) + "."
    return None


def next_steps(
    session: Session, scholarship: Scholarship, today: date
) -> list[NextStep]:
    return [
        NextStep(
            status=target,
            label=LABELS[target],
            blocked_reason=_blocked_reason(session, scholarship, target, today),
            needs_confirmation=target is ApplicationStatus.SUBMITTED,
        )
        for target in TRANSITIONS[current_status(scholarship)]
    ]


def change_status(  # pylint: disable=too-many-arguments
    session: Session,
    user_id: int,
    scholarship_id: int,
    target: ApplicationStatus,
    *,
    confirmed: bool = False,
    note: str | None = None,
    now: datetime | None = None,
) -> Scholarship:
    """Move to `target` if allowed, and record it in the audit log."""
    scholarship = scholarships.get_scholarship(session, user_id, scholarship_id)
    current = current_status(scholarship)
    now = now or datetime.now(UTC)
    if target not in TRANSITIONS[current]:
        raise StatusChangeError(
            f"A scholarship that is {LABELS[current].lower()} can't move to "
            f"{LABELS[target].lower()} directly."
        )
    reason = _blocked_reason(session, scholarship, target, now.date())
    if reason:
        raise StatusChangeError(reason)
    if target is ApplicationStatus.SUBMITTED and not confirmed:
        # FR-A7: submitting happens outside the app, by the student. The app
        # only records it, and only when they explicitly say so.
        raise StatusChangeError(
            "Confirm that you submitted the application yourself before "
            "marking it submitted."
        )
    scholarship.status = target.value
    session.add(
        AuditEvent(
            user_id=user_id,
            scholarship_id=scholarship.id,
            scholarship_name=scholarship.name,
            action=STATUS_CHANGED,
            from_status=current.value,
            to_status=target.value,
            note=(note or "").strip()[:MAX_NOTE] or None,
            created_at=now,
        )
    )
    session.flush()
    return scholarship


def history(session: Session, user_id: int, scholarship_id: int) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.user_id == user_id,
                AuditEvent.scholarship_id == scholarship_id,
            )
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        )
    )

"""Turn what changed into notifications, without repeats (FR-N4, FR-N5).

Called by the daily job after discovery. For each scholarship:

1. Work out its *material state*: the current cycle, deadline, amount,
   eligibility verdict and the set of requirements (by quote).
2. Compare with the state the student was last told about (WatchState).
   * Never seen before -> "new match" (unless it's not a match).
   * Different -> "changed", listing exactly what changed.
   * Same -> nothing. This is what makes re-runs silent.
3. Deadline reminders at 14 and 3 days, keyed by cycle + deadline + threshold,
   so each fires once; if the deadline moves, the key changes.

Preferences only decide whether a notification is *created*; the watch state
is always updated, so turning notifications back on doesn't flood the
student with old news.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.eligibility.engine import Verdict
from app.modules.eligibility.service import (
    ScholarshipEligibility,
    eligibility_for_all,
    quote_key,
)
from app.modules.notify.models import Notification, NotificationKind, WatchState
from app.modules.profile import service as profile
from app.modules.settings import service as settings
from app.modules.tracking.status import ApplicationStatus

REMINDER_DAYS = (3, 14)  # most urgent first
FINISHED = {
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.WON,
    ApplicationStatus.REJECTED,
}
VERDICT_LABELS = {
    Verdict.ELIGIBLE.value: "eligible",
    Verdict.NEEDS_INFO.value: "needs info",
    Verdict.INELIGIBLE.value: "not eligible",
}


def material_state(e: ScholarshipEligibility) -> dict[str, Any]:
    """Only what FR-N4 calls material: deadline, amount, eligibility, requirements."""
    cycle = e.cycle
    return {
        "cycle_id": cycle.id if cycle else None,
        "year": cycle.year if cycle else None,
        "deadline": cycle.deadline.isoformat() if cycle and cycle.deadline else None,
        "amount": cycle.amount_text if cycle else None,
        "verdict": e.result.verdict.value,
        "requirements": sorted(quote_key(c.quote) for c in cycle.criteria)
        if cycle
        else [],
    }


def describe_changes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Plain sentences, e.g. "Deadline: 2027-03-01 → 2027-03-15"."""
    changes = []
    if old.get("year") != new.get("year") and new.get("year"):
        changes.append(f"A {new['year']} cycle is listed.")
    for key, label in (("deadline", "Deadline"), ("amount", "Amount")):
        if old.get(key) != new.get(key):
            before = old.get(key) or "not published"
            after = new.get(key) or "not published"
            changes.append(f"{label}: {before} → {after}.")
    if old.get("verdict") != new.get("verdict"):
        before = VERDICT_LABELS.get(old.get("verdict") or "", "unknown")
        after = VERDICT_LABELS.get(new["verdict"], new["verdict"])
        changes.append(f"Eligibility: {before} → {after}.")
    old_req, new_req = set(old.get("requirements", [])), set(new["requirements"])
    if old_req != new_req:
        added, removed = len(new_req - old_req), len(old_req - new_req)
        parts = [f"{added} added"] if added else []
        parts += [f"{removed} removed"] if removed else []
        changes.append("Requirements changed: " + ", ".join(parts) + ".")
    return changes


def _fingerprint(state: dict[str, Any]) -> str:
    raw = json.dumps(state, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _status(e: ScholarshipEligibility) -> ApplicationStatus:
    try:
        return ApplicationStatus(e.scholarship.status)
    except ValueError:
        return ApplicationStatus.DISCOVERED


def _summary(e: ScholarshipEligibility) -> str:
    parts = [VERDICT_LABELS[e.result.verdict.value].capitalize()]
    if e.cycle and e.cycle.amount_text:
        parts.append(e.cycle.amount_text)
    if e.cycle and e.cycle.deadline:
        parts.append(f"due {e.cycle.deadline.isoformat()}")
    return " · ".join(parts)


@dataclass
class _Run:
    """One generation pass: what's allowed and what was created."""

    session: Session
    user_id: int
    allowed: set[NotificationKind]
    now: datetime
    created: list[Notification]

    def add(  # pylint: disable=too-many-arguments
        self,
        kind: NotificationKind,
        e: ScholarshipEligibility,
        *,
        title: str,
        body: str,
        key: str,
    ) -> None:
        if kind not in self.allowed:
            return
        exists = self.session.scalar(
            select(Notification.id).where(
                Notification.user_id == self.user_id, Notification.dedup_key == key
            )
        )
        if exists:
            return
        notification = Notification(
            user_id=self.user_id,
            scholarship_id=e.scholarship.id,
            kind=kind,
            title=title[:300],
            body=body,
            dedup_key=key[:200],
            created_at=self.now,
        )
        self.session.add(notification)
        self.created.append(notification)


def generate(
    session: Session, user_id: int, *, today: date, now: datetime
) -> list[Notification]:
    """Create the notifications this run deserves. Flushes; caller commits."""
    run = _Run(session, user_id, allowed_kinds(session, user_id), now, [])
    states = {
        w.scholarship_id: w
        for w in session.scalars(
            select(WatchState).where(WatchState.user_id == user_id)
        )
    }
    for e in eligibility_for_all(session, user_id, today):
        new = material_state(e)
        watch = states.get(e.scholarship.id)
        if watch is None:
            _first_sighting(run, e, new, today)
            session.add(
                WatchState(
                    user_id=user_id,
                    scholarship_id=e.scholarship.id,
                    state=new,
                    updated_at=now,
                )
            )
        elif watch.state != new:
            _changed(run, e, watch.state, new)
            watch.state, watch.updated_at = new, now
        _deadline_reminder(run, e, today)
    session.flush()
    return run.created


def _relevant(e: ScholarshipEligibility) -> bool:
    return _status(e) not in FINISHED


def _first_sighting(
    run: _Run, e: ScholarshipEligibility, state: dict[str, Any], today: date
) -> None:
    if not _relevant(e) or e.result.verdict is Verdict.INELIGIBLE:
        return
    if e.cycle and e.cycle.deadline and e.cycle.deadline < today:
        return  # already closed: not news
    run.add(
        NotificationKind.NEW_MATCH,
        e,
        title=f"New match: {e.scholarship.name}",
        body=_summary(e),
        key=f"new:{e.scholarship.id}:{_fingerprint(state)}",
    )


def _changed(
    run: _Run, e: ScholarshipEligibility, old: dict[str, Any], new: dict[str, Any]
) -> None:
    changes = describe_changes(old, new)
    was_match = old.get("verdict") != Verdict.INELIGIBLE.value
    is_match = new["verdict"] != Verdict.INELIGIBLE.value
    if not changes or not _relevant(e) or not (was_match or is_match):
        return  # a non-match staying a non-match isn't worth a message
    run.add(
        NotificationKind.CHANGED,
        e,
        title=f"Changed: {e.scholarship.name}",
        body=" ".join(changes),
        key=f"changed:{e.scholarship.id}:{_fingerprint(new)}",
    )


def _deadline_reminder(run: _Run, e: ScholarshipEligibility, today: date) -> None:
    cycle = e.cycle
    if (
        cycle is None
        or cycle.deadline is None
        or not _relevant(e)
        or e.result.verdict is Verdict.INELIGIBLE
    ):
        return
    days = (cycle.deadline - today).days
    threshold = next((t for t in REMINDER_DAYS if 0 <= days <= t), None)
    if threshold is None:
        return
    when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
    run.add(
        NotificationKind.DEADLINE,
        e,
        title=f"Due {when}: {e.scholarship.name}",
        body=_summary(e),
        key=f"deadline:{cycle.id}:{cycle.deadline.isoformat()}:{threshold}",
    )


# --- Reading and preferences ----------------------------------------------------


def allowed_kinds(session: Session, user_id: int) -> set[NotificationKind]:
    """FR-N5: the master switch on the profile, then each kind's switch."""
    if not profile.get_or_create_profile(session, user_id).notifications_enabled:
        return set()
    prefs = settings.get_settings(session, user_id).notification_kinds
    return {k for k in NotificationKind if prefs.get(k.value, True)}


def list_notifications(
    session: Session, user_id: int, *, unread_only: bool = False, limit: int = 50
) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return list(
        session.scalars(
            query.order_by(
                Notification.created_at.desc(), Notification.id.desc()
            ).limit(limit)
        )
    )


def mark_read(
    session: Session, user_id: int, ids: list[int] | None, *, now: datetime
) -> int:
    """Mark the given notifications (or all) as read. Returns how many."""
    query = select(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if ids is not None:
        query = query.where(Notification.id.in_(ids))
    changed = 0
    for notification in session.scalars(query):
        notification.read_at = now
        changed += 1
    session.flush()
    return changed

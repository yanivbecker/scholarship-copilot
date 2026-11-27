"""The Today screen (FR-UI1): what needs doing, what's due, what's new.

Everything here is derived from existing data on each request: eligibility
(computed fresh), statuses, sources and the last discovery run.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.eligibility.engine import Verdict
from app.modules.eligibility.service import ScholarshipEligibility, eligibility_for_all
from app.modules.jobs.discovery import latest_run
from app.modules.jobs.models import JobRun
from app.modules.profile.catalog import CATALOG
from app.modules.sources import service as sources
from app.modules.tracking.status import ApplicationStatus

DEADLINE_WINDOW_DAYS = 60
SOON_DAYS = 14
NEW_MATCH_DAYS = 7

S = ApplicationStatus
FINISHED = {S.SUBMITTED, S.WON, S.REJECTED}
WORKING_ON = {S.READY_TO_APPLY, S.IN_PROGRESS, S.AWAITING_APPROVAL}


@dataclass(frozen=True)
class Action:
    """One thing the student could do now, and where to do it."""

    kind: str
    title: str
    detail: str
    page: str  # "profile" | "sources" | "scholarship"
    scholarship_id: int | None = None
    fact_key: str | None = None


@dataclass(frozen=True)
class Deadline:
    """An open deadline within the window."""

    scholarship_id: int
    name: str
    deadline: date
    days_left: int
    verdict: str
    status: str


@dataclass(frozen=True)
class NewMatch:
    """A scholarship found recently that the student may qualify for."""

    scholarship_id: int
    name: str
    verdict: str
    found_at: datetime


@dataclass
class Today:
    """Everything the Today screen shows."""

    actions: list[Action] = field(default_factory=list)
    deadlines: list[Deadline] = field(default_factory=list)
    new_matches: list[NewMatch] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    last_run: JobRun | None = None


def _plural(n: int, word: str) -> str:
    """_plural(1, "question") -> "1 question"; _plural(2, ...) -> "2 questions"."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def _status(e: ScholarshipEligibility) -> ApplicationStatus:
    try:
        return ApplicationStatus(e.scholarship.status)
    except ValueError:
        return S.DISCOVERED


def _is_open(e: ScholarshipEligibility, today: date) -> bool:
    deadline = e.cycle.deadline if e.cycle else None
    return deadline is None or deadline >= today


def today_view(session: Session, user_id: int, now: datetime) -> Today:
    today = now.date()
    everything = eligibility_for_all(session, user_id, today)
    view = Today(last_run=latest_run(session, user_id))
    view.counts = dict(Counter(e.result.verdict.value for e in everything))
    view.counts["total"] = len(everything)

    active = [
        e
        for e in everything
        if _status(e) not in FINISHED
        and e.result.verdict is not Verdict.INELIGIBLE
        and _is_open(e, today)
    ]
    view.actions = _actions(session, user_id, active, today)
    view.deadlines = sorted(
        (
            Deadline(
                e.scholarship.id,
                e.scholarship.name,
                e.cycle.deadline,
                (e.cycle.deadline - today).days,
                e.result.verdict.value,
                _status(e).value,
            )
            for e in active
            if e.cycle
            and e.cycle.deadline
            and (e.cycle.deadline - today).days <= DEADLINE_WINDOW_DAYS
        ),
        key=lambda d: d.deadline,
    )
    since = now - timedelta(days=NEW_MATCH_DAYS)
    view.new_matches = [
        NewMatch(
            e.scholarship.id,
            e.scholarship.name,
            e.result.verdict.value,
            e.scholarship.created_at,
        )
        for e in sorted(active, key=lambda e: e.scholarship.created_at, reverse=True)
        if e.scholarship.created_at >= since
    ]
    return view


def _actions(
    session: Session, user_id: int, active: list[ScholarshipEligibility], today: date
) -> list[Action]:
    actions: list[Action] = []

    # Profile facts, ranked by how many scholarships each would help decide.
    needed: Counter[str] = Counter()
    for e in active:
        needed.update({q.fact_key for q in e.result.questions if q.fact_key})
    for key, count in needed.most_common():
        definition = CATALOG.get(key)
        if definition is None:
            continue
        actions.append(
            Action(
                kind="add_fact",
                title=f"Add your {definition.label.lower()}",
                detail=f"Needed to check {_plural(count, 'scholarship')}."
                + (" Optional." if definition.sensitive else ""),
                page="profile",
                fact_key=key,
            )
        )

    for e in active:
        confirmable = [r for r in e.result.questions if r.fact_key is None]
        if confirmable and e.cycle and e.cycle.criteria:
            actions.append(
                Action(
                    kind="confirm_requirements",
                    title=f"Answer {_plural(len(confirmable), 'yes/no question')}",
                    detail=e.scholarship.name,
                    page="scholarship",
                    scholarship_id=e.scholarship.id,
                )
            )
        if e.result.verdict is Verdict.ELIGIBLE and _status(e) is S.DISCOVERED:
            actions.append(
                Action(
                    kind="confirm_eligibility",
                    title="You meet every requirement: mark eligibility confirmed",
                    detail=e.scholarship.name,
                    page="scholarship",
                    scholarship_id=e.scholarship.id,
                )
            )
        if e.scholarship.needs_review:
            actions.append(
                Action(
                    kind="review",
                    title="Review this listing",
                    detail=e.scholarship.review_reason or e.scholarship.name,
                    page="scholarship",
                    scholarship_id=e.scholarship.id,
                )
            )
        deadline = e.cycle.deadline if e.cycle else None
        if (
            deadline
            and _status(e) in WORKING_ON
            and (deadline - today).days <= SOON_DAYS
        ):
            days = (deadline - today).days
            actions.append(
                Action(
                    kind="deadline_soon",
                    title=f"Due in {_plural(days, 'day')}",
                    detail=e.scholarship.name,
                    page="scholarship",
                    scholarship_id=e.scholarship.id,
                )
            )

    for source in sources.list_sources(session, user_id):
        if source.last_result == "login_required":
            actions.append(
                Action(
                    kind="paste_text",
                    title="Paste a listing that needs a login",
                    detail=source.label or source.url,
                    page="sources",
                )
            )
    return actions

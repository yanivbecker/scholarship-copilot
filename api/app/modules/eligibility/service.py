"""Eligibility for stored scholarships: always computed fresh (FR-E4).

Verdicts aren't stored. They're computed from the current profile and the
current criteria every time they're read, so a changed fact or a
re-extracted page is reflected immediately. The engine is pure Python and
fast enough to evaluate every scholarship on each request.
"""

import hashlib
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.eligibility.engine import CriterionInput, EligibilityResult, evaluate
from app.modules.eligibility.models import CriterionConfirmation
from app.modules.eligibility.scoring import PriorityScore, priority_score
from app.modules.profile import repository as profile_repository
from app.modules.profile.catalog import FactValue
from app.modules.scholarships import service as scholarships
from app.modules.scholarships.criteria import CriterionKind
from app.modules.scholarships.evidence import normalize_for_matching
from app.modules.scholarships.models import Criterion, Scholarship, ScholarshipCycle


class CriterionNotFoundError(LookupError):
    """No such criterion on this scholarship."""


class NotConfirmableError(ValueError):
    """Only free-text criteria are confirmed by the student. User-facing."""


@dataclass(frozen=True)
class ScholarshipEligibility:
    """The verdict for a scholarship's current cycle, with its score."""

    scholarship: Scholarship
    cycle: ScholarshipCycle | None
    result: EligibilityResult
    score: PriorityScore
    as_of: date


def quote_key(quote: str) -> str:
    return hashlib.sha256(normalize_for_matching(quote).encode()).hexdigest()


def current_cycle(scholarship: Scholarship, today: date) -> ScholarshipCycle | None:
    """The cycle that matters now: the soonest open deadline, else the newest."""
    if not scholarship.cycles:
        return None
    open_cycles = [c for c in scholarship.cycles if c.deadline and c.deadline >= today]
    if open_cycles:
        return min(open_cycles, key=lambda c: c.deadline or today)
    return max(scholarship.cycles, key=lambda c: c.year)


def facts_for(session: Session, user_id: int) -> dict[str, FactValue]:
    return {f.key: f.value for f in profile_repository.list_facts(session, user_id)}


def confirmations_for(session: Session, user_id: int) -> dict[tuple[int, str], bool]:
    rows = session.scalars(
        select(CriterionConfirmation).where(CriterionConfirmation.user_id == user_id)
    )
    return {(r.scholarship_id, r.quote_key): r.answer for r in rows}


def evaluate_scholarship(
    scholarship: Scholarship,
    *,
    facts: dict[str, FactValue],
    confirmations: dict[tuple[int, str], bool],
    today: date,
) -> ScholarshipEligibility:
    cycle = current_cycle(scholarship, today)
    criteria = cycle.criteria if cycle else []
    inputs = [
        CriterionInput(
            id=c.id,
            kind=c.kind,
            params=c.params,
            quote=c.quote,
            confirmation=confirmations.get((scholarship.id, quote_key(c.quote))),
        )
        for c in criteria
    ]
    # Age limits count on the deadline; otherwise today.
    as_of = cycle.deadline if cycle and cycle.deadline else today
    result = evaluate(inputs, facts, as_of)
    amount = (cycle.amount_max or cycle.amount_min) if cycle else None
    score = priority_score(
        result,
        amount=amount,
        deadline=cycle.deadline if cycle else None,
        today=today,
        warning_signs=len(scholarship.scam_flags),
    )
    return ScholarshipEligibility(scholarship, cycle, result, score, as_of)


def eligibility_for(
    session: Session, user_id: int, scholarship_id: int, today: date
) -> ScholarshipEligibility:
    scholarship = scholarships.get_scholarship(session, user_id, scholarship_id)
    return evaluate_scholarship(
        scholarship,
        facts=facts_for(session, user_id),
        confirmations=confirmations_for(session, user_id),
        today=today,
    )


def eligibility_for_all(
    session: Session, user_id: int, today: date
) -> list[ScholarshipEligibility]:
    """Every scholarship, best priority first."""
    facts = facts_for(session, user_id)
    confirmations = confirmations_for(session, user_id)
    evaluated = [
        evaluate_scholarship(s, facts=facts, confirmations=confirmations, today=today)
        for s in scholarships.list_scholarships(session, user_id)
    ]
    return sorted(evaluated, key=lambda e: (-e.score.total, e.scholarship.name))


def set_confirmation(
    session: Session,
    user_id: int,
    scholarship_id: int,
    criterion_id: int,
    answer: bool | None,
) -> None:
    """FR-E3: the student says whether they meet a free-text requirement.

    `answer=None` removes the answer (back to "unknown").
    """
    scholarship = scholarships.get_scholarship(session, user_id, scholarship_id)
    criterion = session.scalars(
        select(Criterion)
        .join(ScholarshipCycle)
        .where(
            Criterion.id == criterion_id,
            ScholarshipCycle.scholarship_id == scholarship.id,
            Criterion.user_id == user_id,
        )
    ).first()
    if criterion is None:
        raise CriterionNotFoundError(f"No criterion {criterion_id}")
    if criterion.kind != CriterionKind.FREE_TEXT.value:
        raise NotConfirmableError(
            "This requirement is checked against your profile. Update your "
            "profile instead."
        )
    key = quote_key(criterion.quote)
    existing = session.scalars(
        select(CriterionConfirmation).where(
            CriterionConfirmation.user_id == user_id,
            CriterionConfirmation.scholarship_id == scholarship.id,
            CriterionConfirmation.quote_key == key,
        )
    ).first()
    if answer is None:
        if existing is not None:
            session.delete(existing)
    elif existing is None:
        session.add(
            CriterionConfirmation(
                user_id=user_id,
                scholarship_id=scholarship.id,
                quote_key=key,
                answer=answer,
            )
        )
    else:
        existing.answer = answer
    session.flush()

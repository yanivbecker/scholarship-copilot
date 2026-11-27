"""Eligibility verdicts, computed fresh on every request (FR-E1-E6)."""

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.modules.eligibility import service
from app.modules.eligibility.schemas import (
    ConfirmationIn,
    CriterionResultOut,
    EligibilityOut,
    QuestionOut,
    ScoreOut,
    ScorePartOut,
)
from app.modules.scholarships.criteria import CriterionKind
from app.modules.tracking.service import current_status
from app.modules.tracking.status import LABELS

router = APIRouter(tags=["eligibility"])


def _today() -> datetime:
    return datetime.now(UTC)


def _out(e: service.ScholarshipEligibility) -> EligibilityOut:
    criteria = {c.id: c for c in (e.cycle.criteria if e.cycle else [])}
    status = current_status(e.scholarship)
    return EligibilityOut(
        scholarship_id=e.scholarship.id,
        name=e.scholarship.name,
        sponsor=e.scholarship.sponsor,
        status=status.value,
        status_label=LABELS[status],
        amount=(e.cycle.amount_max or e.cycle.amount_min) if e.cycle else None,
        amount_text=e.cycle.amount_text if e.cycle else None,
        open_questions=len(e.result.questions),
        cycle_id=e.cycle.id if e.cycle else None,
        year=e.cycle.year if e.cycle else None,
        deadline=e.cycle.deadline if e.cycle else None,
        verdict=e.result.verdict.value,
        summary=e.result.summary,
        as_of=e.as_of,
        criteria=[
            CriterionResultOut(
                criterion_id=r.criterion_id,
                kind=criteria[r.criterion_id].kind,
                quote=criteria[r.criterion_id].quote,
                source_url=criteria[r.criterion_id].source_url,
                outcome=r.outcome.value,
                reason=r.reason,
                question=QuestionOut(**asdict(r.question)) if r.question else None,
                confirmable=criteria[r.criterion_id].kind
                == CriterionKind.FREE_TEXT.value,
            )
            for r in e.result.results
        ],
        questions=[QuestionOut(**asdict(q)) for q in e.result.questions],
        score=ScoreOut(
            total=e.score.total,
            note=e.score.note,
            parts=[ScorePartOut(**asdict(p)) for p in e.score.parts],
        ),
    )


@router.get("/eligibility")
def list_eligibility(session: SessionDep, user: CurrentUser) -> list[EligibilityOut]:
    """Every scholarship, highest priority first."""
    today = _today().date()
    return [_out(e) for e in service.eligibility_for_all(session, user.id, today)]


@router.get("/scholarships/{scholarship_id}/eligibility")
def get_eligibility(
    scholarship_id: int, session: SessionDep, user: CurrentUser
) -> EligibilityOut:
    today = _today().date()
    return _out(service.eligibility_for(session, user.id, scholarship_id, today))


@router.put("/scholarships/{scholarship_id}/criteria/{criterion_id}/confirmation")
def confirm_criterion(
    scholarship_id: int,
    criterion_id: int,
    body: ConfirmationIn,
    session: SessionDep,
    user: CurrentUser,
) -> EligibilityOut:
    """FR-E3: answer a free-text requirement; returns the updated verdict."""
    service.set_confirmation(
        session, user.id, scholarship_id, criterion_id, body.answer
    )
    session.commit()
    today = _today().date()
    return _out(service.eligibility_for(session, user.id, scholarship_id, today))

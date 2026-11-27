"""Application status tracking (FR-UI4) with an audit log (FR-A7)."""

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.modules.scholarships import service as scholarships
from app.modules.tracking import service
from app.modules.tracking.schemas import (
    AuditEventOut,
    NextStepOut,
    StatusChangeIn,
    StatusOut,
)
from app.modules.tracking.status import LABELS

router = APIRouter(tags=["tracking"])


def _status_out(session: SessionDep, user_id: int, scholarship_id: int) -> StatusOut:
    scholarship = scholarships.get_scholarship(session, user_id, scholarship_id)
    current = service.current_status(scholarship)
    today = datetime.now(UTC).date()
    return StatusOut(
        status=current,
        label=LABELS[current],
        next_steps=[
            NextStepOut(**asdict(step))
            for step in service.next_steps(session, scholarship, today)
        ],
        history=[
            AuditEventOut.model_validate(e)
            for e in service.history(session, user_id, scholarship_id)
        ],
    )


@router.get("/scholarships/{scholarship_id}/status")
def get_status(
    scholarship_id: int, session: SessionDep, user: CurrentUser
) -> StatusOut:
    return _status_out(session, user.id, scholarship_id)


@router.post("/scholarships/{scholarship_id}/status")
def change_status(
    scholarship_id: int, body: StatusChangeIn, session: SessionDep, user: CurrentUser
) -> StatusOut:
    service.change_status(
        session,
        user.id,
        scholarship_id,
        body.status,
        confirmed=body.confirmed,
        note=body.note,
    )
    session.commit()
    return _status_out(session, user.id, scholarship_id)

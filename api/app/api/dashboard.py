"""The Today screen (FR-UI1)."""

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.modules.dashboard.schemas import (
    ActionOut,
    DeadlineOut,
    NewMatchOut,
    TodayOut,
)
from app.modules.dashboard.service import today_view
from app.modules.jobs.schemas import JobRunOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/today")
def get_today(session: SessionDep, user: CurrentUser) -> TodayOut:
    view = today_view(session, user.id, datetime.now(UTC))
    return TodayOut(
        actions=[ActionOut(**asdict(a)) for a in view.actions],
        deadlines=[DeadlineOut(**asdict(d)) for d in view.deadlines],
        new_matches=[NewMatchOut(**asdict(m)) for m in view.new_matches],
        counts=view.counts,
        last_run=JobRunOut.model_validate(view.last_run) if view.last_run else None,
    )

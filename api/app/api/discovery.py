"""Run discovery now (FR-N2 "Run now") and see the last run (FR-UI1)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SessionDep
from app.core.config import get_settings
from app.api.scholarships import AIDep
from app.api.sources import FetcherDep
from app.modules.jobs.daily import run_daily
from app.modules.jobs.discovery import latest_run
from app.modules.jobs.schemas import JobRunOut
from app.modules.sources.search import Searcher, get_searcher

SearcherDep = Annotated[Searcher | None, Depends(get_searcher)]

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/run")
def run_now(
    session: SessionDep,
    user: CurrentUser,
    fetcher: FetcherDep,
    ai: AIDep,
    searcher: SearcherDep,
) -> JobRunOut:
    """Run the daily job now (FR-N2 "Run now": works even with background
    running off). Can take a while: each site is contacted at most once per
    second, and AI extraction is slow."""
    result = run_daily(
        session,
        user_id=user.id,
        fetcher=fetcher,
        provider=ai,
        trigger="api",
        searcher=searcher,
        search_interval_days=get_settings().search_interval_days,
    )
    run = result.run or latest_run(session, user.id)
    if run is None:  # pragma: no cover - run_discovery always records a run
        raise RuntimeError("The run was not recorded.")
    return JobRunOut.model_validate(run)


@router.get("/runs/latest")
def get_latest_run(session: SessionDep, user: CurrentUser) -> JobRunOut | None:
    run = latest_run(session, user.id)
    return JobRunOut.model_validate(run) if run else None

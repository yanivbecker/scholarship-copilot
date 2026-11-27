"""Run discovery now (FR-N2 "Run now") and see the last run (FR-UI1)."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.scholarships import AIDep
from app.api.sources import FetcherDep
from app.modules.jobs.discovery import latest_run, run_discovery
from app.modules.jobs.schemas import JobRunOut

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/run")
def run_now(
    session: SessionDep, user: CurrentUser, fetcher: FetcherDep, ai: AIDep
) -> JobRunOut:
    """Check every source and extract what changed. Can take a while: each
    site is contacted at most once per second, and AI extraction is slow."""
    run = run_discovery(
        session, user_id=user.id, fetcher=fetcher, provider=ai, trigger="api"
    )
    return JobRunOut.model_validate(run)


@router.get("/runs/latest")
def get_latest_run(session: SessionDep, user: CurrentUser) -> JobRunOut | None:
    run = latest_run(session, user.id)
    return JobRunOut.model_validate(run) if run else None

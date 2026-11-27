"""Response body for the Today screen (FR-UI1)."""

from datetime import date, datetime

from pydantic import BaseModel

from app.modules.jobs.schemas import JobRunOut


class ActionOut(BaseModel):
    """Something to do now, and where (`page`) to do it."""

    kind: str
    title: str
    detail: str
    page: str
    scholarship_id: int | None
    fact_key: str | None


class DeadlineOut(BaseModel):
    """An open deadline within the next 60 days."""

    scholarship_id: int
    name: str
    deadline: date
    days_left: int
    verdict: str
    status: str


class NewMatchOut(BaseModel):
    """A scholarship found in the last 7 days."""

    scholarship_id: int
    name: str
    verdict: str
    found_at: datetime


class TodayOut(BaseModel):
    """Actions needed, upcoming deadlines, new matches, last run (FR-UI1)."""

    actions: list[ActionOut]
    deadlines: list[DeadlineOut]
    new_matches: list[NewMatchOut]
    counts: dict[str, int]
    last_run: JobRunOut | None

"""Response bodies for scholarships (a minimal list; the dashboard is Phase 6)."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.scholarships.criteria import CriterionKind


class _FromORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CriterionOut(_FromORM):
    """One requirement, with the exact words it came from (FR-D5)."""

    id: int
    kind: CriterionKind
    params: dict[str, Any]
    quote: str
    source_url: str


class CycleOut(_FromORM):
    """One year of a scholarship (FR-D8)."""

    id: int
    year: int
    amount_text: str | None
    amount_min: int | None
    amount_max: int | None
    deadline: date | None
    deadline_quote: str | None
    source_url: str
    extracted_by: str
    extracted_at: datetime
    criteria: list[CriterionOut]


class ScamFlagOut(BaseModel):
    """A warning sign and the text that triggered it (FR-D9)."""

    signal: str
    evidence: str


class ScholarshipOut(_FromORM):
    """A scholarship with its cycles, newest first."""

    id: int
    name: str
    sponsor: str | None
    official_url: str | None
    description: str | None
    status: str
    scam_flags: list[ScamFlagOut]
    needs_review: bool
    review_reason: str | None
    cycles: list[CycleOut]


class ExtractionReportOut(BaseModel):
    """What an extraction did."""

    status: str
    message: str
    created: int
    updated: int
    criteria_saved: int
    criteria_rejected: int
    scholarships_rejected: int


class DuplicateOut(BaseModel):
    """Two scholarships that may be the same one (FR-D6)."""

    first_id: int
    first_name: str
    second_id: int
    second_name: str
    score: float


class MergeIn(BaseModel):
    """Merge `other_id` into the scholarship in the URL."""

    other_id: int

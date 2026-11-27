"""Response bodies for eligibility (FR-E1-E6)."""

from datetime import date

from pydantic import BaseModel


class QuestionOut(BaseModel):
    """Answer this to resolve an unknown. `fact_key`: answer in the profile."""

    text: str
    fact_key: str | None
    optional: bool


class CriterionResultOut(BaseModel):
    """One requirement, its evidence, and how it compares with the profile."""

    criterion_id: int
    kind: str
    quote: str
    source_url: str
    outcome: str  # met | not_met | unknown
    reason: str
    question: QuestionOut | None
    confirmable: bool  # free text: the student answers it directly (FR-E3)


class ScorePartOut(BaseModel):
    """One ingredient of the priority score and what it's based on."""

    name: str
    value: float
    basis: str  # listing | estimate
    detail: str


class ScoreOut(BaseModel):
    """0-100 priority. Our ranking, not the chance of winning (FR-E6)."""

    total: int
    note: str
    parts: list[ScorePartOut]


class EligibilityOut(BaseModel):
    """The verdict for a scholarship's current cycle (FR-E2)."""

    scholarship_id: int
    name: str
    sponsor: str | None
    status: str  # application status (FR-UI4)
    status_label: str
    amount: int | None  # the larger published amount, if any
    amount_text: str | None
    open_questions: int  # a rough effort signal (FR-UI2)
    cycle_id: int | None
    year: int | None
    deadline: date | None
    verdict: str  # eligible | ineligible | needs_info
    summary: str
    as_of: date
    criteria: list[CriterionResultOut]
    questions: list[QuestionOut]
    score: ScoreOut


class ConfirmationIn(BaseModel):
    """Do you meet this free-text requirement? null clears the answer."""

    answer: bool | None

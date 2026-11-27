"""Request and response bodies for resume import."""

from pydantic import BaseModel

from app.modules.profile.schemas import FactValueIn, FactValueOut


class SuggestionOut(BaseModel):
    """A suggested fact, the resume line it came from, and what's on file now."""

    key: str
    label: str
    value: FactValueOut
    evidence: str
    current_value: FactValueOut | None


class ResumeUploadOut(BaseModel):
    """The stored resume and the facts suggested from it. Nothing is saved yet."""

    document_id: int
    filename: str
    suggestions: list[SuggestionOut]


class ResumeConfirmIn(BaseModel):
    """The suggestions the student accepted, with any edits they made."""

    facts: dict[str, FactValueIn]

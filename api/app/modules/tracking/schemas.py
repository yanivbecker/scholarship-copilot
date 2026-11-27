"""Request and response bodies for status tracking."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tracking.status import ApplicationStatus


class NextStepOut(BaseModel):
    """A status this scholarship can move to (or why it can't yet)."""

    status: ApplicationStatus
    label: str
    blocked_reason: str | None
    needs_confirmation: bool


class AuditEventOut(BaseModel):
    """One recorded change."""

    model_config = ConfigDict(from_attributes=True)

    action: str
    from_status: str | None
    to_status: str | None
    note: str | None
    created_at: datetime


class StatusOut(BaseModel):
    """Current status, possible next steps, and the history (FR-UI4)."""

    status: ApplicationStatus
    label: str
    next_steps: list[NextStepOut]
    history: list[AuditEventOut]


class StatusChangeIn(BaseModel):
    """Move to `status`. Submitting needs `confirmed: true` (FR-A7)."""

    status: ApplicationStatus
    confirmed: bool = False
    note: str | None = Field(default=None, max_length=500)

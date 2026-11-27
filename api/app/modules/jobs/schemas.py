"""Response bodies for job runs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobRunOut(BaseModel):
    """One discovery run and what it did."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    summary: dict[str, Any]
    error: str | None

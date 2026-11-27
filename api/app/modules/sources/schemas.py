"""Request and response bodies for the sources API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.sources.models import SourceStatus


class SourceIn(BaseModel):
    """A page to add. Checked by url_safety before it's stored."""

    url: str
    label: str | None = None


class SourceOut(BaseModel):
    """A stored source. `url` is the normalized form."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    label: str | None
    status: SourceStatus
    created_at: datetime

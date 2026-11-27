"""Request and response bodies for the sources API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.sources.models import SnapshotOrigin, SourceStatus


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
    last_checked_at: datetime | None
    last_result: str | None
    last_message: str | None
    last_changed_at: datetime | None


class CheckOut(BaseModel):
    """The source after a check, and whether its text changed."""

    source: SourceOut
    skipped: bool
    changed: bool


class PasteIn(BaseModel):
    """Listing text copied from a page that needs a login (FR-D4)."""

    text: str


class SnapshotOut(BaseModel):
    """The most recent text stored for a source."""

    model_config = ConfigDict(from_attributes=True)

    origin: SnapshotOrigin
    url: str
    content_type: str | None
    text: str
    changed: bool
    fetched_at: datetime

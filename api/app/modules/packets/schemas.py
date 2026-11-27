"""Request and response bodies for application packets (Phase 7)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.packets.models import ItemKind, LimitUnit, RulesStatus, VersionOrigin


class VersionOut(BaseModel):
    """One saved version, with its length against the item's limit."""

    id: int
    number: int
    text: str
    origin: VersionOrigin
    provenance: list[dict[str, Any]] | None
    created_at: datetime
    approved_at: datetime | None
    chars: int
    words: int
    over_limit: bool


class ItemOut(BaseModel):
    """One thing the application needs, and the student's work on it."""

    id: int
    kind: ItemKind
    title: str
    prompt: str | None
    prompt_source_url: str | None
    limit_value: int | None
    limit_unit: LimitUnit | None
    required: bool
    done: bool
    finished: bool
    approved_version_id: int | None
    versions: list[VersionOut]


class ProgressOut(BaseModel):
    """Required items finished so far, and the titles still missing."""

    finished: int
    required: int
    missing: list[str]
    complete: bool


class PacketOut(BaseModel):
    """The whole packet for one scholarship cycle."""

    id: int
    scholarship_id: int
    cycle_id: int
    rules_status: RulesStatus
    rules_quote: str | None
    rules_source_url: str | None
    rules_confirmed_at: datetime | None
    ai_writing_allowed: bool
    approved_at: datetime | None
    progress: ProgressOut
    items: list[ItemOut]


class ItemIn(BaseModel):
    """Create or edit an item. `done` ticks off documents and form fields."""

    kind: ItemKind
    title: str
    prompt: str | None = None
    limit_value: int | None = None
    limit_unit: LimitUnit | None = None
    required: bool = True
    done: bool | None = None


class VersionIn(BaseModel):
    """A new version of a response, written by the student."""

    text: str = Field(max_length=50_000)


class UseLibraryIn(BaseModel):
    """Start an item's response from a library entry."""

    entry_id: int


class LibraryEntryOut(BaseModel):
    """An approved response kept for reuse (FR-A8)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    prompt: str | None
    text: str
    scholarship_name: str
    created_at: datetime

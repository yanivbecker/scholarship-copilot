"""Request and response bodies for notifications and their settings."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.notify.models import NotificationKind


class NotificationOut(BaseModel):
    """One in-app notification."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scholarship_id: int | None
    kind: NotificationKind
    title: str
    body: str
    created_at: datetime
    read_at: datetime | None


class NotificationsOut(BaseModel):
    """Recent notifications, newest first, and how many are unread."""

    items: list[NotificationOut]
    unread: int


class MarkReadIn(BaseModel):
    """Which notifications to mark read; leave out `ids` for all of them."""

    ids: list[int] | None = Field(default=None, max_length=500)


class NotificationKindsIn(BaseModel):
    """FR-N5: turn each kind of notification on or off."""

    kinds: dict[NotificationKind, bool]


class SearchQueriesIn(BaseModel):
    """FR-N3: the exact queries the student approves for web search."""

    queries: list[str] = Field(max_length=10)


class SettingsOut(BaseModel):
    """Background, notification and search settings."""

    background_enabled: bool
    notifications_enabled: bool
    notification_kinds: dict[NotificationKind, bool]
    search_queries: list[str]
    suggested_queries: list[str]
    search_configured: bool
    last_search_at: datetime | None

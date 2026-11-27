"""Notifications (FR-N4, FR-N5) and background settings (FR-N2, FR-N3)."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.core.config import get_settings as get_app_settings
from app.modules.notify import service as notify
from app.modules.notify.models import NotificationKind
from app.modules.notify.schemas import (
    MarkReadIn,
    NotificationKindsIn,
    NotificationOut,
    NotificationsOut,
    SearchQueriesIn,
    SettingsOut,
)
from app.modules.profile import service as profile
from app.modules.settings import service as user_settings
from app.modules.sources.search import suggest_queries

router = APIRouter(tags=["notifications"])


def settings_out(session: SessionDep, user_id: int) -> SettingsOut:
    row = user_settings.get_settings(session, user_id)
    return SettingsOut(
        background_enabled=row.background_enabled,
        notifications_enabled=profile.get_or_create_profile(
            session, user_id
        ).notifications_enabled,
        notification_kinds={
            k: row.notification_kinds.get(k.value, True) for k in NotificationKind
        },
        search_queries=row.search_queries,
        suggested_queries=suggest_queries(session, user_id),
        search_configured=get_app_settings().tavily_api_key is not None,
        last_search_at=row.last_search_at,
    )


@router.get("/notifications")
def list_notifications(
    session: SessionDep, user: CurrentUser, unread_only: bool = False
) -> NotificationsOut:
    items = notify.list_notifications(session, user.id, unread_only=unread_only)
    unread = len(
        notify.list_notifications(session, user.id, unread_only=True, limit=500)
    )
    return NotificationsOut(
        items=[NotificationOut.model_validate(n) for n in items], unread=unread
    )


@router.post("/notifications/read")
def mark_notifications_read(
    body: MarkReadIn, session: SessionDep, user: CurrentUser
) -> NotificationsOut:
    notify.mark_read(session, user.id, body.ids, now=datetime.now(UTC))
    session.commit()
    return list_notifications(session, user)


@router.get("/settings")
def get_settings(session: SessionDep, user: CurrentUser) -> SettingsOut:
    out = settings_out(session, user.id)
    session.commit()  # the settings row may have just been created
    return out


@router.put("/settings/notifications")
def set_notification_kinds(
    body: NotificationKindsIn, session: SessionDep, user: CurrentUser
) -> SettingsOut:
    user_settings.set_notification_kinds(
        session,
        user.id,
        {k.value: v for k, v in body.kinds.items()},
        known={k.value for k in NotificationKind},
    )
    session.commit()
    return settings_out(session, user.id)


@router.put("/settings/search-queries")
def set_search_queries(
    body: SearchQueriesIn, session: SessionDep, user: CurrentUser
) -> SettingsOut:
    """FR-N3: nothing is sent to search until the student saves queries here."""
    user_settings.set_search_queries(session, user.id, body.queries)
    session.commit()
    return settings_out(session, user.id)

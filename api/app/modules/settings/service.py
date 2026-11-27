"""Read and change per-user settings (FR-N2, FR-N3, FR-N5)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.settings.models import UserSettings

MAX_QUERIES = 10
MAX_QUERY_CHARS = 200


class SettingsError(ValueError):
    """An invalid setting. The message is user-facing."""


def get_settings(session: Session, user_id: int) -> UserSettings:
    row = session.scalars(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()
    if row is None:
        row = UserSettings(
            user_id=user_id,
            background_enabled=True,
            notification_kinds={},
            search_queries=[],
        )
        session.add(row)
        session.flush()
    return row


def set_notification_kinds(
    session: Session, user_id: int, kinds: dict[str, bool], *, known: set[str]
) -> UserSettings:
    unknown = set(kinds) - known
    if unknown:
        raise SettingsError(f"Unknown notification types: {sorted(unknown)}.")
    row = get_settings(session, user_id)
    row.notification_kinds = {**row.notification_kinds, **kinds}
    session.flush()
    return row


def set_search_queries(
    session: Session, user_id: int, queries: list[str]
) -> UserSettings:
    """FR-N3: the exact queries the student approved for sending to search."""
    clean = list(dict.fromkeys(" ".join(q.split()) for q in queries if q.strip()))
    if len(clean) > MAX_QUERIES:
        raise SettingsError(f"Up to {MAX_QUERIES} search queries.")
    if any(len(q) > MAX_QUERY_CHARS for q in clean):
        raise SettingsError(f"Each query can be at most {MAX_QUERY_CHARS} characters.")
    row = get_settings(session, user_id)
    row.search_queries = clean
    session.flush()
    return row


def set_background(session: Session, user_id: int, enabled: bool) -> UserSettings:
    row = get_settings(session, user_id)
    row.background_enabled = enabled
    session.flush()
    return row

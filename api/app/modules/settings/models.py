"""Per-user settings for background work (FR-N2, FR-N3, FR-N5)."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import UTCDateTime


class UserSettings(Base):
    """One row per user, created on first use with safe defaults."""

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    # FR-N2: scheduled runs do nothing while this is off. "Run now" still works.
    background_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true()
    )
    # FR-N5: kind -> on/off. Missing kinds are on.
    notification_kinds: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)
    # FR-N3: only queries the student wrote or saved are ever sent to search.
    search_queries: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_search_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

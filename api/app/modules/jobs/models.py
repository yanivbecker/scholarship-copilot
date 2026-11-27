"""A record of every background or manual job run (ARCHITECTURE rule 3)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import UTCDateTime


class JobRun(Base):
    """One run of a job such as `scholar discover`."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))  # "discover"
    trigger: Mapped[str] = mapped_column(String(20))  # "cli" | "api" | "schedule"
    status: Mapped[str] = mapped_column(String(20))  # running|succeeded|partial|failed
    started_at: Mapped[datetime] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

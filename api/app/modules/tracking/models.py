"""The audit log: who changed what, and when (FR-A7).

Status changes (and, in Phase 7, approvals) are recorded here. Rows keep the
scholarship's name, so the history still reads correctly if that scholarship
is later merged into another (scholarship_id is then set to NULL).
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import UTCDateTime


class AuditEvent(Base):  # pylint: disable=too-many-instance-attributes
    """One recorded action."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scholarship_id: Mapped[int | None] = mapped_column(
        ForeignKey("scholarships.id", ondelete="SET NULL"), index=True
    )
    scholarship_name: Mapped[str] = mapped_column(String(300))
    action: Mapped[str] = mapped_column(String(40))  # "status_changed", ...
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

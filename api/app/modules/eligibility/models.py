"""The student's own answers to free-text criteria (FR-E3).

Keyed by the requirement's wording (a hash of its normalized quote), not the
criterion row: re-extracting the same page recreates criteria rows, and the
answer should survive that. If the sponsor rewords the requirement, the hash
changes and the student is asked again, which is what we want.
"""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import UTCDateTime


class CriterionConfirmation(Base):
    """ "I meet this requirement" (or "I don't") for one scholarship."""

    __tablename__ = "criterion_confirmations"
    __table_args__ = (UniqueConstraint("user_id", "scholarship_id", "quote_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scholarship_id: Mapped[int] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), index=True
    )
    quote_key: Mapped[str] = mapped_column(String(64))
    answer: Mapped[bool] = mapped_column(Boolean)
    confirmed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

"""Adding, listing and removing sources. Services don't commit (see profile)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.sources.models import Source, SourceStatus
from app.modules.sources.url_safety import UnsafeURLError, normalize_source_url

MAX_LABEL_LENGTH = 200


class SourceNotFoundError(LookupError):
    """No such source for this user."""


class DuplicateSourceError(ValueError):
    """The source is already on the list. The message is user-facing."""


def add_source(
    session: Session, user_id: int, *, url: str, label: str | None = None
) -> Source:
    """FR-D1: the student adds a source by hand, so it starts out approved."""
    normalized = normalize_source_url(url)  # raises UnsafeURLError
    clean_label = (label or "").strip() or None
    if clean_label and len(clean_label) > MAX_LABEL_LENGTH:
        raise UnsafeURLError(f"Name must be at most {MAX_LABEL_LENGTH} characters.")
    existing = session.scalars(
        select(Source).where(Source.user_id == user_id, Source.url == normalized)
    ).first()
    if existing is not None:
        raise DuplicateSourceError("That source is already on your list.")
    source = Source(
        user_id=user_id,
        url=normalized,
        label=clean_label,
        status=SourceStatus.APPROVED,
    )
    session.add(source)
    session.flush()
    return source


def list_sources(session: Session, user_id: int) -> list[Source]:
    return list(
        session.scalars(
            select(Source).where(Source.user_id == user_id).order_by(Source.id)
        )
    )


def delete_source(session: Session, user_id: int, source_id: int) -> None:
    source = session.scalars(
        select(Source).where(Source.user_id == user_id, Source.id == source_id)
    ).first()
    if source is None:
        raise SourceNotFoundError(f"No source {source_id}")
    session.delete(source)
    session.flush()

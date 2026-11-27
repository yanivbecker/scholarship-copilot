"""Adding, listing and removing sources. Services don't commit (see profile)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.fetcher.fetcher import FetchStatus, PoliteFetcher
from app.modules.fetcher.text import content_hash
from app.modules.sources.models import (
    PageSnapshot,
    SnapshotOrigin,
    Source,
    SourceStatus,
)
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


class ReviewError(ValueError):
    """The source isn't waiting for review. The message is user-facing."""


def review_source(
    session: Session, user_id: int, source_id: int, *, approve: bool
) -> Source:
    """FR-D1: the student approves or rejects a suggested page. A rejected
    page stays on record (hidden), so search never suggests it again."""
    source = get_source(session, user_id, source_id)
    if source.status is not SourceStatus.PENDING_REVIEW:
        raise ReviewError("Only suggested pages can be approved or rejected.")
    source.status = SourceStatus.APPROVED if approve else SourceStatus.REJECTED
    session.flush()
    return source


def delete_source(session: Session, user_id: int, source_id: int) -> None:
    session.delete(get_source(session, user_id, source_id))
    session.flush()


# --- Checking sources (5.1) ---------------------------------------------------

KEEP_SNAPSHOTS = 5
MAX_PASTE_CHARS = 200_000

# Results that won't change by retrying automatically. A person can still
# press "Check now" (force=True), e.g. after a site removes its login wall.
SKIP_AUTOMATIC = frozenset(
    {
        FetchStatus.LOGIN_REQUIRED,
        FetchStatus.ROBOTS_DISALLOWED,
        FetchStatus.BLOCKED_URL,
    }
)
PASTED = "pasted"


class PasteError(ValueError):
    """Pasted text can't be used. The message is user-facing."""


@dataclass(frozen=True)
class CheckOutcome:
    """What a check did. `snapshot` is set when new text was stored."""

    source: Source
    skipped: bool = False
    changed: bool = False
    snapshot: PageSnapshot | None = None


def get_source(session: Session, user_id: int, source_id: int) -> Source:
    source = session.scalars(
        select(Source).where(Source.user_id == user_id, Source.id == source_id)
    ).first()
    if source is None:
        raise SourceNotFoundError(f"No source {source_id}")
    return source


def latest_snapshot(session: Session, source_id: int) -> PageSnapshot | None:
    return session.scalars(
        select(PageSnapshot)
        .where(PageSnapshot.source_id == source_id)
        .order_by(PageSnapshot.fetched_at.desc(), PageSnapshot.id.desc())
    ).first()


def check_source(  # pylint: disable=too-many-arguments
    session: Session,
    fetcher: PoliteFetcher,
    user_id: int,
    source_id: int,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> CheckOutcome:
    """Fetch an approved source and store its text if it changed."""
    source = get_source(session, user_id, source_id)
    if source.status is not SourceStatus.APPROVED:
        return CheckOutcome(source, skipped=True)
    if not force and source.last_result in SKIP_AUTOMATIC:
        return CheckOutcome(source, skipped=True)

    now = now or datetime.now(UTC)
    result = fetcher.fetch(
        source.url, etag=source.etag, last_modified=source.last_modified
    )
    source.last_checked_at = now
    source.last_result = result.status.value
    source.last_message = result.message[:500] or None

    outcome = CheckOutcome(source)
    if result.status is FetchStatus.OK and result.text and result.content_hash:
        source.etag = result.etag
        source.last_modified = result.last_modified
        snapshot = _store_snapshot(
            session,
            source,
            origin=SnapshotOrigin.FETCHED,
            url=result.url,
            content_type=result.content_type,
            text=result.text,
            text_hash=result.content_hash,
            now=now,
        )
        outcome = CheckOutcome(source, changed=snapshot.changed, snapshot=snapshot)
    session.flush()
    return outcome


def paste_source_text(
    session: Session,
    user_id: int,
    source_id: int,
    text: str,
    *,
    now: datetime | None = None,
) -> CheckOutcome:
    """FR-D4: the student pastes a listing they can see behind a login."""
    source = get_source(session, user_id, source_id)
    if not text.strip():
        raise PasteError("Paste the listing text first.")
    if len(text) > MAX_PASTE_CHARS:
        raise PasteError(f"That's more than {MAX_PASTE_CHARS:,} characters.")
    now = now or datetime.now(UTC)
    snapshot = _store_snapshot(
        session,
        source,
        origin=SnapshotOrigin.PASTED,
        url=source.url,
        content_type="text/plain",
        text=text,
        text_hash=content_hash(text),
        now=now,
    )
    source.last_checked_at = now
    source.last_result = PASTED
    source.last_message = "Text pasted by you."
    session.flush()
    return CheckOutcome(source, changed=snapshot.changed, snapshot=snapshot)


def _store_snapshot(  # pylint: disable=too-many-arguments
    session: Session,
    source: Source,
    *,
    origin: SnapshotOrigin,
    url: str,
    content_type: str | None,
    text: str,
    text_hash: str,
    now: datetime,
) -> PageSnapshot:
    previous = latest_snapshot(session, source.id)
    changed = previous is None or previous.content_hash != text_hash
    snapshot = PageSnapshot(
        source_id=source.id,
        user_id=source.user_id,
        origin=origin,
        url=url,
        content_type=content_type,
        content_hash=text_hash,
        text=text,
        changed=changed,
        fetched_at=now,
    )
    session.add(snapshot)
    if changed:
        source.last_changed_at = now
    session.flush()
    _prune_snapshots(session, source.id)
    return snapshot


def _prune_snapshots(session: Session, source_id: int) -> None:
    """Keep only the newest few snapshots per source."""
    old = session.scalars(
        select(PageSnapshot)
        .where(PageSnapshot.source_id == source_id)
        .order_by(PageSnapshot.fetched_at.desc(), PageSnapshot.id.desc())
        .offset(KEEP_SNAPSHOTS)
    ).all()
    for snapshot in old:
        session.delete(snapshot)

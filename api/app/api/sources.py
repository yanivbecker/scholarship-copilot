"""Scholarship sources the student approves (FR-D1), checking them (FR-D2),
and pasting listings from login-only portals (FR-D4)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.modules.fetcher.fetcher import PoliteFetcher
from app.modules.sources import service
from app.modules.sources.models import Source
from app.modules.sources.schemas import (
    CheckOut,
    PasteIn,
    SnapshotOut,
    SourceIn,
    SourceOut,
)

router = APIRouter(prefix="/sources", tags=["sources"])


def get_fetcher() -> Iterator[PoliteFetcher]:
    """A fetcher for this request. Tests override it with a fake web."""
    fetcher = PoliteFetcher()
    try:
        yield fetcher
    finally:
        fetcher.close()


FetcherDep = Annotated[PoliteFetcher, Depends(get_fetcher)]


def _source_out(session: SessionDep, source: Source) -> SourceOut:
    out = SourceOut.model_validate(source)
    snapshot = service.latest_snapshot(session, source.id)
    if snapshot is not None:
        out.extraction_status = snapshot.extraction_status
        out.extraction_message = snapshot.extraction_message
    return out


def _check_out(session: SessionDep, outcome: service.CheckOutcome) -> CheckOut:
    return CheckOut(
        source=_source_out(session, outcome.source),
        skipped=outcome.skipped,
        changed=outcome.changed,
    )


@router.get("")
def list_sources(session: SessionDep, user: CurrentUser) -> list[SourceOut]:
    return [_source_out(session, s) for s in service.list_sources(session, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_source(body: SourceIn, session: SessionDep, user: CurrentUser) -> SourceOut:
    source = service.add_source(session, user.id, url=body.url, label=body.label)
    session.commit()
    return SourceOut.model_validate(source)


@router.post("/{source_id}/check")
def check_source(
    source_id: int, session: SessionDep, user: CurrentUser, fetcher: FetcherDep
) -> CheckOut:
    """Check now. A person asked, so known dead ends are retried too."""
    outcome = service.check_source(session, fetcher, user.id, source_id, force=True)
    session.commit()
    return _check_out(session, outcome)


class ReviewIn(BaseModel):
    """Approve (check it from now on) or reject (never suggest it again)."""

    approve: bool


@router.post("/{source_id}/review")
def review_source(
    source_id: int, body: ReviewIn, session: SessionDep, user: CurrentUser
) -> SourceOut:
    source = service.review_source(session, user.id, source_id, approve=body.approve)
    session.commit()
    return SourceOut.model_validate(source)


@router.post("/{source_id}/paste")
def paste_source_text(
    source_id: int, body: PasteIn, session: SessionDep, user: CurrentUser
) -> CheckOut:
    outcome = service.paste_source_text(session, user.id, source_id, body.text)
    session.commit()
    return _check_out(session, outcome)


@router.get("/{source_id}/snapshot")
def get_latest_snapshot(
    source_id: int, session: SessionDep, user: CurrentUser
) -> SnapshotOut | None:
    service.get_source(session, user.id, source_id)  # 404 if not theirs
    snapshot = service.latest_snapshot(session, source_id)
    return SnapshotOut.model_validate(snapshot) if snapshot else None


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, session: SessionDep, user: CurrentUser) -> Response:
    service.delete_source(session, user.id, source_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

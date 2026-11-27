"""Scholarship sources the student approves (FR-D1). Fetching is Phase 5."""

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.modules.sources import service
from app.modules.sources.schemas import SourceIn, SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources(session: SessionDep, user: CurrentUser) -> list[SourceOut]:
    return [SourceOut.model_validate(s) for s in service.list_sources(session, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_source(body: SourceIn, session: SessionDep, user: CurrentUser) -> SourceOut:
    source = service.add_source(session, user.id, url=body.url, label=body.label)
    session.commit()
    return SourceOut.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, session: SessionDep, user: CurrentUser) -> Response:
    service.delete_source(session, user.id, source_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

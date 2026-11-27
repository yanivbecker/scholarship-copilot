"""Resume import (FR-P2): upload a PDF/DOCX, review suggestions, confirm."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.core.storage import FileStorage, get_storage
from app.modules.profile.catalog import get_definition
from app.modules.profile.schemas import FactOut
from app.modules.resume import service
from app.modules.resume.extract import Suggestion
from app.modules.resume.files import MAX_UPLOAD_BYTES, ResumeFileError
from app.modules.resume.schemas import ResumeConfirmIn, ResumeUploadOut, SuggestionOut

router = APIRouter(prefix="/resume", tags=["resume"])

StorageDep = Annotated[FileStorage, Depends(get_storage)]


def _suggestions_out(
    suggestions: list[Suggestion], current: dict[str, object]
) -> list[SuggestionOut]:
    return [
        SuggestionOut(
            key=s.key,
            label=get_definition(s.key).label,
            value=s.value,
            evidence=s.evidence,
            current_value=current.get(s.key),  # type: ignore[arg-type]
        )
        for s in suggestions
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile, session: SessionDep, user: CurrentUser, storage: StorageDep
) -> ResumeUploadOut:
    # Read at most one byte past the limit, so a huge upload is never held
    # in memory in full.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ResumeFileError("The file is larger than 5 MB.")
    document, suggestions = service.upload_resume(
        session, storage, user.id, filename=file.filename, data=data
    )
    session.commit()
    return ResumeUploadOut(
        document_id=document.id,
        filename=document.original_filename,
        suggestions=_suggestions_out(
            suggestions, service.current_values(session, user.id)
        ),
    )


@router.post("/{document_id}/confirm")
def confirm_resume_facts(
    document_id: int,
    body: ResumeConfirmIn,
    session: SessionDep,
    user: CurrentUser,
    storage: StorageDep,
) -> list[FactOut]:
    facts = service.confirm_facts(
        session, storage, user.id, document_id, dict(body.facts)
    )
    session.commit()
    return [FactOut.model_validate(f) for f in facts]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    document_id: int, session: SessionDep, user: CurrentUser, storage: StorageDep
) -> Response:
    service.delete_resume(session, storage, user.id, document_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

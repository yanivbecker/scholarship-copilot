"""Resume import (FR-P2): upload, suggest facts, confirm each one.

Provenance is decided by the server, not the browser: on confirm we read the
stored file again and re-run the (deterministic) extraction. A value saved
unchanged gets origin RESUME; a value the student edited gets origin MANUAL.
So "From your resume" in the profile is always literally true.
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import FileStorage
from app.modules.documents.models import Document
from app.modules.profile import repository as profile_repository
from app.modules.profile import service as profile_service
from app.modules.profile.catalog import FieldErrorsError, validate_facts
from app.modules.profile.models import FactOrigin, ProfileFact
from app.modules.resume.extract import Suggestion, suggest_facts
from app.modules.resume.files import clean_filename, read_resume

RESUME = "resume"


class ResumeNotFoundError(LookupError):
    """No such resume for this user."""


class ResumeConfirmError(FieldErrorsError):
    """Some confirmed values can't be saved. `field_errors` says which."""


def upload_resume(
    session: Session,
    storage: FileStorage,
    user_id: int,
    *,
    filename: str | None,
    data: bytes,
) -> tuple[Document, list[Suggestion]]:
    """Check and store the file, and return suggestions. Saves no facts."""
    resume = read_resume(data)  # raises ResumeFileError before anything is stored
    key = storage.save(data, suffix=f".{resume.kind}")
    document = Document(
        user_id=user_id,
        kind=RESUME,
        original_filename=clean_filename(filename),
        storage_key=key,
        content_type=resume.content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    session.add(document)
    session.flush()
    return document, suggest_facts(resume.text)


def get_resume(session: Session, user_id: int, document_id: int) -> Document:
    document = session.scalars(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.kind == RESUME,
        )
    ).first()
    if document is None:
        raise ResumeNotFoundError(f"No resume {document_id}")
    return document


def suggestions_for(storage: FileStorage, document: Document) -> list[Suggestion]:
    return suggest_facts(read_resume(storage.read(document.storage_key)).text)


def confirm_facts(
    session: Session,
    storage: FileStorage,
    user_id: int,
    document_id: int,
    facts: dict[str, object],
) -> list[ProfileFact]:
    """Save the facts the student accepted (possibly edited). All or nothing."""
    document = get_resume(session, user_id, document_id)
    extracted = {s.key: s.value for s in suggestions_for(storage, document)}

    # Only facts this resume actually contains can be saved as "from resume".
    clean, errors = validate_facts(
        facts,
        is_allowed=lambda key: key in extracted,
        not_allowed_message=lambda _key: (
            "This wasn't found in the resume. Add it on your profile."
        ),
    )
    if errors:
        raise ResumeConfirmError("Some values need fixing.", errors)

    saved = []
    name = document.original_filename
    for key, value in clean.items():
        unchanged = value == extracted[key]
        saved.append(
            profile_service.set_fact(
                session,
                user_id,
                key,
                value,
                origin=FactOrigin.RESUME if unchanged else FactOrigin.MANUAL,
                origin_detail=name if unchanged else f"edited from {name}",
            )
        )
    return saved


def current_values(session: Session, user_id: int) -> dict[str, object]:
    """What's on file now, so the confirm screen can show "replaces X"."""
    return {f.key: f.value for f in profile_repository.list_facts(session, user_id)}


def delete_resume(
    session: Session, storage: FileStorage, user_id: int, document_id: int
) -> None:
    """Remove the file and its record. Facts already confirmed stay."""
    document = get_resume(session, user_id, document_id)
    storage.delete(document.storage_key)
    session.delete(document)
    session.flush()

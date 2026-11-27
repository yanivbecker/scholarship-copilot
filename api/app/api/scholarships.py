"""Scholarships found on sources, and running extraction (FR-D5, FR-D8)."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.base import AIProvider
from app.ai.factory import get_ai_provider
from app.api.deps import CurrentUser, SessionDep
from app.modules.scholarships import service
from app.modules.scholarships import merge
from app.modules.scholarships.schemas import (
    DuplicateOut,
    ExtractionReportOut,
    MergeIn,
    ScholarshipOut,
)
from app.modules.sources import service as sources

router = APIRouter(tags=["scholarships"])

AIDep = Annotated[AIProvider, Depends(get_ai_provider)]


@router.get("/scholarships")
def list_scholarships(session: SessionDep, user: CurrentUser) -> list[ScholarshipOut]:
    return [
        ScholarshipOut.model_validate(s)
        for s in service.list_scholarships(session, user.id)
    ]


@router.get("/scholarships/duplicates")
def list_possible_duplicates(
    session: SessionDep, user: CurrentUser
) -> list[DuplicateOut]:
    """Pairs that may be the same scholarship, for the student to decide."""
    return [
        DuplicateOut(
            first_id=d.first.id,
            first_name=d.first.name,
            second_id=d.second.id,
            second_name=d.second.name,
            score=d.score,
        )
        for d in merge.possible_duplicates(session, user.id)
    ]


@router.post("/scholarships/{scholarship_id}/merge")
def merge_scholarship(
    scholarship_id: int, body: MergeIn, session: SessionDep, user: CurrentUser
) -> ScholarshipOut:
    kept = merge.merge_scholarships(session, user.id, scholarship_id, body.other_id)
    session.commit()
    return ScholarshipOut.model_validate(
        service.get_scholarship(session, user.id, kept.id)
    )


@router.get("/scholarships/{scholarship_id}")
def get_scholarship(
    scholarship_id: int, session: SessionDep, user: CurrentUser
) -> ScholarshipOut:
    return ScholarshipOut.model_validate(
        service.get_scholarship(session, user.id, scholarship_id)
    )


@router.post("/sources/{source_id}/extract")
def extract_source(
    source_id: int, session: SessionDep, user: CurrentUser, ai: AIDep
) -> ExtractionReportOut:
    """Extract from the source's latest text now (even if unchanged)."""
    source = sources.get_source(session, user.id, source_id)
    snapshot = service.latest_snapshot_for(session, source)
    if snapshot is None:
        raise sources.PasteError(
            "There's no text for this source yet. Check it or paste the listing first."
        )
    report = service.extract_snapshot(session, ai, snapshot, force=True)
    session.commit()
    fields = asdict(report)
    fields["status"] = report.status.value
    return ExtractionReportOut.model_validate(fields)

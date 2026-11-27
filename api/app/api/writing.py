"""AI writing help (FR-A3, FR-A4) and the claim check (FR-A5).

Coaching and drafting are refused (403) unless the packet's AI-use rules
were confirmed as allowed. The claim check uses no AI, so it's always on.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.base import AIProvider
from app.ai.factory import get_ai_provider
from app.api.deps import CurrentUser, SessionDep
from app.api.packets import packet_out
from app.modules.packets import service, writing
from app.modules.packets.models import PacketItem
from app.modules.packets.provenance import check_claims, gather_material
from app.modules.packets.schemas import (
    DraftIn,
    DraftOut,
    FeedbackIn,
    FeedbackOut,
    OutlineIn,
    ProvenanceOut,
    RemovedSentenceOut,
    SentenceCheckOut,
)

router = APIRouter(tags=["writing"])
AIDep = Annotated[AIProvider, Depends(get_ai_provider)]


def _item(session: SessionDep, user_id: int, item_id: int) -> PacketItem:
    return service.get_item(session, user_id, item_id)


@router.post("/packet-items/{item_id}/coach/breakdown")
def coach_breakdown(
    item_id: int, session: SessionDep, user: CurrentUser, ai: AIDep
) -> writing.Breakdown:
    item = _item(session, user.id, item_id)
    return writing.breakdown(ai, item.packet, item)


@router.post("/packet-items/{item_id}/coach/questions")
def coach_questions(
    item_id: int, session: SessionDep, user: CurrentUser, ai: AIDep
) -> writing.Questions:
    item = _item(session, user.id, item_id)
    return writing.interview_questions(ai, item.packet, item)


@router.post("/packet-items/{item_id}/coach/outline")
def coach_outline(
    item_id: int, body: OutlineIn, session: SessionDep, user: CurrentUser, ai: AIDep
) -> writing.Outline:
    item = _item(session, user.id, item_id)
    answers = [writing.Answer(a.question, a.answer) for a in body.answers]
    return writing.outline(
        ai, session, item.packet, item, answers, story_ids=body.story_ids
    )


@router.post("/packet-items/{item_id}/coach/feedback")
def coach_feedback(
    item_id: int, body: FeedbackIn, session: SessionDep, user: CurrentUser, ai: AIDep
) -> FeedbackOut:
    item = _item(session, user.id, item_id)
    notes, length_note = writing.feedback(ai, item.packet, item, body.version_id)
    return FeedbackOut(notes=notes.notes, length_note=length_note)


@router.post("/packet-items/{item_id}/draft")
def draft_response(
    item_id: int, body: DraftIn, session: SessionDep, user: CurrentUser, ai: AIDep
) -> DraftOut:
    """FR-A4: a draft from chosen facts and stories, saved as a new version."""
    item = _item(session, user.id, item_id)
    result = writing.draft(
        ai,
        session,
        item.packet,
        item,
        fact_keys=body.fact_keys,
        story_ids=body.story_ids,
    )
    session.commit()
    return DraftOut(
        packet=packet_out(session, item.packet),
        version_id=result.version_id,
        kept=result.kept,
        removed=[
            RemovedSentenceOut(text=r.text, reason=r.reason) for r in result.removed
        ],
    )


@router.get("/packet-items/{item_id}/versions/{version_id}/claims")
def check_version_claims(
    item_id: int, version_id: int, session: SessionDep, user: CurrentUser
) -> ProvenanceOut:
    """FR-A5: highlight numbers and names not found in your facts or stories."""
    item = _item(session, user.id, item_id)
    version = next((v for v in item.versions if v.id == version_id), None)
    if version is None:
        raise service.PacketNotFoundError(f"No version {version_id}")
    checks = check_claims(version.text, gather_material(session, user.id))
    return ProvenanceOut(
        sentences=[
            SentenceCheckOut(sentence=c.sentence, unsupported=list(c.unsupported))
            for c in checks
        ],
        unsupported_count=sum(len(c.unsupported) for c in checks),
    )

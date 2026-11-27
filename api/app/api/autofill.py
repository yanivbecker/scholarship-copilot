"""What the browser extension reads, and how it reports a fill (FR-X1, FR-A7).

The extension reaches these through its host permission for 127.0.0.1, so no
CORS is enabled: websites still can't read this API from a browser tab.
"""

from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.modules.packets import autofill, service
from app.modules.packets.models import ItemKind

router = APIRouter(prefix="/autofill", tags=["autofill"])


class ApprovedPacketOut(BaseModel):
    """An approved packet the extension can fill from."""

    packet_id: int
    scholarship_id: int
    name: str
    hosts: list[str]
    approved_at: datetime


class FillEntryOut(BaseModel):
    """One approved answer. The extension matches `title`/`prompt` to a field."""

    item_id: int
    kind: ItemKind
    title: str
    prompt: str | None
    text: str


class FillSheetOut(BaseModel):
    """Everything the extension may type into one application."""

    packet_id: int
    scholarship_name: str
    official_url: str | None
    entries: list[FillEntryOut]


class FillReportIn(BaseModel):
    """What the extension did: counts and the site's host only, no page content."""

    host: str = Field(min_length=1, max_length=253)
    filled: int = Field(ge=0, le=500)
    unmatched: int = Field(ge=0, le=500)


@router.get("/packets")
def list_approved_packets(
    session: SessionDep, user: CurrentUser
) -> list[ApprovedPacketOut]:
    return [
        ApprovedPacketOut(
            packet_id=p.packet_id,
            scholarship_id=p.scholarship_id,
            name=p.name,
            hosts=list(p.hosts),
            approved_at=p.approved_at,
        )
        for p in autofill.approved_packets(session, user.id)
    ]


@router.get("/packets/{packet_id}")
def get_fill_sheet(
    packet_id: int, session: SessionDep, user: CurrentUser
) -> FillSheetOut:
    sheet = autofill.fill_sheet(
        session, service.get_packet(session, user.id, packet_id)
    )
    return FillSheetOut(
        packet_id=sheet.packet_id,
        scholarship_name=sheet.scholarship_name,
        official_url=sheet.official_url,
        entries=[
            FillEntryOut(
                item_id=e.item_id,
                kind=e.kind,
                title=e.title,
                prompt=e.prompt,
                text=e.text,
            )
            for e in sheet.entries
        ],
    )


@router.post("/packets/{packet_id}/fills", status_code=status.HTTP_204_NO_CONTENT)
def report_fill(
    packet_id: int, body: FillReportIn, session: SessionDep, user: CurrentUser
) -> None:
    packet = service.get_packet(session, user.id, packet_id)
    autofill.fill_sheet(session, packet)  # only approved packets are ever filled
    autofill.record_fill(
        session, packet, host=body.host, filled=body.filled, unmatched=body.unmatched
    )
    session.commit()

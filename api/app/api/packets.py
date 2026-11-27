"""Application packets: checklist, responses, approvals, library (FR-A6-A8)."""

from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.modules.packets import service
from app.modules.packets.models import Packet, PacketItem
from app.modules.packets.rules import ai_writing_allowed, confirm_rules, scan_rules
from app.modules.scholarships import service as scholarships
from app.modules.packets.schemas import (
    ItemIn,
    ItemOut,
    LibraryEntryOut,
    PacketOut,
    ProgressOut,
    RulesIn,
    RulesScanOut,
    UseLibraryIn,
    VersionIn,
    VersionOut,
)

router = APIRouter(tags=["packets"])


def _item_out(item: PacketItem) -> ItemOut:
    approved = service.approved_version(item)
    versions = []
    for v in item.versions:
        length = service.check_length(item, v.text)
        versions.append(
            VersionOut(
                id=v.id,
                number=v.number,
                text=v.text,
                origin=v.origin,
                provenance=v.provenance,
                created_at=v.created_at,
                approved_at=v.approved_at,
                chars=length.chars,
                words=length.words,
                over_limit=length.over_limit,
            )
        )
    return ItemOut(
        id=item.id,
        kind=item.kind,
        title=item.title,
        prompt=item.prompt,
        prompt_source_url=item.prompt_source_url,
        limit_value=item.limit_value,
        limit_unit=item.limit_unit,
        required=item.required,
        done=item.done,
        finished=service.item_finished(item),
        approved_version_id=approved.id if approved else None,
        versions=versions,
    )


def packet_out(session: SessionDep, packet: Packet) -> PacketOut:
    session.refresh(packet)
    state = service.progress(packet)
    return PacketOut(
        id=packet.id,
        scholarship_id=packet.scholarship_id,
        cycle_id=packet.cycle_id,
        rules_status=packet.rules_status,
        rules_quote=packet.rules_quote,
        rules_source_url=packet.rules_source_url,
        rules_confirmed_at=packet.rules_confirmed_at,
        ai_writing_allowed=ai_writing_allowed(packet),
        approved_at=packet.approved_at,
        progress=ProgressOut(
            finished=state.finished,
            required=state.required,
            missing=list(state.missing),
            complete=state.complete,
        ),
        items=[_item_out(i) for i in packet.items],
    )


def _fields(body: ItemIn) -> service.ItemFields:
    return service.ItemFields(
        kind=body.kind,
        title=body.title,
        prompt=body.prompt,
        limit_value=body.limit_value,
        limit_unit=body.limit_unit,
        required=body.required,
    )


@router.get("/scholarships/{scholarship_id}/packet")
def get_packet(
    scholarship_id: int, session: SessionDep, user: CurrentUser
) -> PacketOut:
    packet = service.get_or_create_packet(
        session, user.id, scholarship_id, datetime.now(UTC).date()
    )
    session.commit()
    return packet_out(session, packet)


@router.post("/packets/{packet_id}/items", status_code=status.HTTP_201_CREATED)
def add_item(
    packet_id: int, body: ItemIn, session: SessionDep, user: CurrentUser
) -> PacketOut:
    packet = service.get_packet(session, user.id, packet_id)
    service.add_item(session, packet, _fields(body))
    session.commit()
    return packet_out(session, packet)


@router.put("/packet-items/{item_id}")
def update_item(
    item_id: int, body: ItemIn, session: SessionDep, user: CurrentUser
) -> PacketOut:
    item = service.get_item(session, user.id, item_id)
    service.update_item(session, item, _fields(body), done=body.done)
    session.commit()
    return packet_out(session, item.packet)


@router.delete("/packet-items/{item_id}")
def delete_item(item_id: int, session: SessionDep, user: CurrentUser) -> PacketOut:
    item = service.get_item(session, user.id, item_id)
    packet = item.packet
    service.delete_item(session, item)
    session.commit()
    return packet_out(session, packet)


@router.post("/packet-items/{item_id}/versions", status_code=status.HTTP_201_CREATED)
def save_version(
    item_id: int, body: VersionIn, session: SessionDep, user: CurrentUser
) -> PacketOut:
    item = service.get_item(session, user.id, item_id)
    service.save_version(session, item, body.text)
    session.commit()
    return packet_out(session, item.packet)


@router.post("/packet-items/{item_id}/versions/{version_id}/approve")
def approve_version(
    item_id: int, version_id: int, session: SessionDep, user: CurrentUser
) -> PacketOut:
    item = service.get_item(session, user.id, item_id)
    service.approve_version(session, item, version_id)
    session.commit()
    return packet_out(session, item.packet)


@router.post("/packet-items/{item_id}/use-library", status_code=status.HTTP_201_CREATED)
def use_library(
    item_id: int, body: UseLibraryIn, session: SessionDep, user: CurrentUser
) -> PacketOut:
    item = service.get_item(session, user.id, item_id)
    service.use_library_entry(session, item, body.entry_id)
    session.commit()
    return packet_out(session, item.packet)


@router.get("/library")
def list_library(session: SessionDep, user: CurrentUser) -> list[LibraryEntryOut]:
    return [
        LibraryEntryOut.model_validate(e)
        for e in service.list_library(session, user.id)
    ]


@router.post("/packets/{packet_id}/approve")
def approve_packet(packet_id: int, session: SessionDep, user: CurrentUser) -> PacketOut:
    packet = service.get_packet(session, user.id, packet_id)
    service.approve_packet(session, packet)
    session.commit()
    return packet_out(session, packet)


@router.delete("/packets/{packet_id}/approve")
def withdraw_approval(
    packet_id: int, session: SessionDep, user: CurrentUser
) -> PacketOut:
    packet = service.get_packet(session, user.id, packet_id)
    service.withdraw_packet_approval(session, packet)
    session.commit()
    return packet_out(session, packet)


@router.get("/packets/{packet_id}/rules/scan")
def scan_packet_rules(
    packet_id: int, session: SessionDep, user: CurrentUser
) -> RulesScanOut:
    """FR-A1: find what the sponsor says about AI use. Changes nothing."""
    packet = service.get_packet(session, user.id, packet_id)
    scan = scan_rules(session, packet)
    return RulesScanOut(
        suggested=scan.suggested,
        candidates=list(scan.candidates),
        source_url=scan.source_url,
        has_text=scan.has_text,
    )


@router.put("/packets/{packet_id}/rules")
def confirm_packet_rules(
    packet_id: int, body: RulesIn, session: SessionDep, user: CurrentUser
) -> PacketOut:
    """FR-A2: the student confirms the rules before any writing help."""
    packet = service.get_packet(session, user.id, packet_id)
    name = scholarships.get_scholarship(session, user.id, packet.scholarship_id).name
    confirm_rules(session, packet, body.status, quote=body.quote, scholarship_name=name)
    session.commit()
    return packet_out(session, packet)

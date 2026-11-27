"""Run extraction on a snapshot and save the verified results.

Only snapshots whose text changed are extracted automatically (FR-D7).
Failures are recorded on the snapshot, never hidden:
  * needs_ai: AI is off or unreachable (NFR-6). Add details by hand.
  * needs_review: the AI refused or returned invalid output twice (NFR-5).
  * too_long: the page is too long to send; paste the relevant part instead.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.base import AIError, AIProvider, AIUnavailableError
from app.ai.structured import ask_structured
from app.modules.scholarships.dedup import Candidate, is_same_scholarship
from app.modules.scholarships.evidence import normalize_for_matching
from app.modules.scholarships.extraction import (
    SYSTEM_PROMPT,
    ExtractionOutput,
    VerifiedScholarship,
    build_user_prompt,
    verify,
)
from app.modules.scholarships.models import Criterion, Scholarship, ScholarshipCycle
from app.modules.scholarships.scam import find_scam_flags
from app.modules.sources.models import PageSnapshot, Source

MAX_EXTRACTION_CHARS = 60_000  # about 15k tokens


class ExtractionStatus(StrEnum):
    """Stored on the snapshot after an extraction attempt."""

    DONE = "done"
    NO_SCHOLARSHIPS = "no_scholarships"
    UNCHANGED = "unchanged"  # FR-D7: same text as before, not re-extracted
    NEEDS_AI = "needs_ai"
    NEEDS_REVIEW = "needs_review"
    TOO_LONG = "too_long"


@dataclass
class ExtractionReport:  # pylint: disable=too-many-instance-attributes
    """What one extraction did, for the API, jobs and job_runs (5.5)."""

    status: ExtractionStatus
    message: str = ""
    created: int = 0
    updated: int = 0
    criteria_saved: int = 0
    criteria_rejected: int = 0
    scholarships_rejected: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class ScholarshipNotFoundError(LookupError):
    """No such scholarship for this user."""


def match_key(name: str, sponsor: str | None) -> str:
    """Exact-match identity: same name + sponsor = same scholarship."""
    return f"{normalize_for_matching(name)}|{normalize_for_matching(sponsor or '')}"


def extract_snapshot(  # pylint: disable=too-many-arguments
    session: Session,
    provider: AIProvider,
    snapshot: PageSnapshot,
    *,
    force: bool = False,
    today: date | None = None,
    now: datetime | None = None,
) -> ExtractionReport:
    """Extract scholarships from one snapshot. Commits nothing (caller does)."""
    now = now or datetime.now(UTC)
    today = today or now.date()
    report = _extract(session, provider, snapshot, force=force, today=today, now=now)
    snapshot.extraction_status = report.status.value
    snapshot.extraction_message = report.message[:500] or None
    snapshot.extracted_at = now
    session.flush()
    return report


def _extract(  # pylint: disable=too-many-arguments
    session: Session,
    provider: AIProvider,
    snapshot: PageSnapshot,
    *,
    force: bool,
    today: date,
    now: datetime,
) -> ExtractionReport:
    if not force and not snapshot.changed:
        return ExtractionReport(ExtractionStatus.UNCHANGED, "Text unchanged.")
    if len(snapshot.text) > MAX_EXTRACTION_CHARS:
        return ExtractionReport(
            ExtractionStatus.TOO_LONG,
            "The page is too long to process. Paste the part about the "
            "scholarship instead.",
        )
    try:
        result = ask_structured(
            provider,
            system=SYSTEM_PROMPT,
            user=build_user_prompt(snapshot.text, source_url=snapshot.url, today=today),
            output=ExtractionOutput,
        )
    except AIUnavailableError as exc:
        return ExtractionReport(ExtractionStatus.NEEDS_AI, str(exc))
    except AIError as exc:
        return ExtractionReport(ExtractionStatus.NEEDS_REVIEW, str(exc))

    verified = verify(result.value, text=snapshot.text, today=today)
    report = ExtractionReport(
        ExtractionStatus.DONE
        if verified.scholarships
        else ExtractionStatus.NO_SCHOLARSHIPS,
        scholarships_rejected=verified.rejected_scholarships,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    model_name = result.replies[-1].model
    flags = [
        {"signal": f.signal.value, "evidence": f.evidence}
        for f in find_scam_flags(snapshot.text)
    ]
    for item in verified.scholarships:
        created = _save(session, snapshot, item, flags=flags, model=model_name, now=now)
        report.created += int(created)
        report.updated += int(not created)
        report.criteria_saved += len(item.criteria)
        report.criteria_rejected += item.rejected_criteria
    report.message = _summary(report)
    return report


def _save(  # pylint: disable=too-many-arguments
    session: Session,
    snapshot: PageSnapshot,
    item: VerifiedScholarship,
    *,
    flags: list[dict[str, str]],
    model: str,
    now: datetime,
) -> bool:
    """Create or update the scholarship and this year's cycle. True if new."""
    key = match_key(item.name, item.sponsor)
    scholarship = find_existing(session, snapshot.user_id, item, key)
    created = scholarship is None
    if scholarship is None:
        scholarship = Scholarship(
            user_id=snapshot.user_id, name=item.name, match_key=key, scam_flags=[]
        )
        session.add(scholarship)
    scholarship.sponsor = item.sponsor or scholarship.sponsor
    # Only the scholarship's own page; the listing page is cycle.source_url.
    scholarship.official_url = item.official_url or scholarship.official_url
    scholarship.description = item.description or scholarship.description
    known = {f["signal"] for f in scholarship.scam_flags}
    scholarship.scam_flags = scholarship.scam_flags + [
        f for f in flags if f["signal"] not in known
    ]
    if item.notes:
        scholarship.needs_review = True
        scholarship.review_reason = " ".join(item.notes)[:500]
    session.flush()

    cycle = session.scalars(
        select(ScholarshipCycle).where(
            ScholarshipCycle.scholarship_id == scholarship.id,
            ScholarshipCycle.year == item.year,
        )
    ).first()
    if cycle is None:
        cycle = ScholarshipCycle(
            scholarship_id=scholarship.id, user_id=snapshot.user_id, year=item.year
        )
        session.add(cycle)
    # The newest source of this year's details wins, criteria included.
    cycle.amount_text = item.amount_text
    cycle.amount_min = item.amount_min
    cycle.amount_max = item.amount_max
    cycle.deadline = item.deadline
    cycle.deadline_quote = item.deadline_quote
    cycle.source_id = snapshot.source_id
    cycle.source_url = snapshot.url
    cycle.extracted_by = model
    cycle.extracted_at = now
    cycle.criteria = [
        Criterion(
            user_id=snapshot.user_id,
            position=position,
            kind=c.kind.value,
            params=c.params,
            quote=c.quote,
            source_url=snapshot.url,
        )
        for position, c in enumerate(item.criteria)
    ]
    session.flush()
    return created


def find_existing(
    session: Session, user_id: int, item: VerifiedScholarship, key: str
) -> Scholarship | None:
    """The stored scholarship this one is, if any (FR-D6).

    Exact identity first; otherwise a near-certain fuzzy match (dedup.py).
    """
    exact = session.scalars(
        select(Scholarship).where(
            Scholarship.user_id == user_id, Scholarship.match_key == key
        )
    ).first()
    if exact is not None:
        return exact
    new = Candidate(item.name, item.sponsor, item.official_url)
    for existing in session.scalars(
        select(Scholarship)
        .where(Scholarship.user_id == user_id)
        .order_by(Scholarship.id)
    ):
        if is_same_scholarship(
            new, Candidate(existing.name, existing.sponsor, existing.official_url)
        ):
            return existing
    return None


def _summary(report: ExtractionReport) -> str:
    found = report.created + report.updated
    parts = [f"{found} scholarship{'s' if found != 1 else ''} found"]
    if report.criteria_rejected:
        parts.append(
            f"{report.criteria_rejected} criteria rejected (quote not on page)"
        )
    if report.scholarships_rejected:
        parts.append(f"{report.scholarships_rejected} rejected (name not on page)")
    return "; ".join(parts) + "."


# --- Reading ----------------------------------------------------------------


def list_scholarships(session: Session, user_id: int) -> list[Scholarship]:
    return list(
        session.scalars(
            select(Scholarship)
            .where(Scholarship.user_id == user_id)
            .options(
                selectinload(Scholarship.cycles).selectinload(ScholarshipCycle.criteria)
            )
            .order_by(Scholarship.name)
        )
    )


def get_scholarship(session: Session, user_id: int, scholarship_id: int) -> Scholarship:
    scholarship = session.scalars(
        select(Scholarship)
        .where(Scholarship.user_id == user_id, Scholarship.id == scholarship_id)
        .options(
            selectinload(Scholarship.cycles).selectinload(ScholarshipCycle.criteria)
        )
    ).first()
    if scholarship is None:
        raise ScholarshipNotFoundError(f"No scholarship {scholarship_id}")
    return scholarship


def latest_snapshot_for(session: Session, source: Source) -> PageSnapshot | None:
    return session.scalars(
        select(PageSnapshot)
        .where(PageSnapshot.source_id == source.id)
        .order_by(PageSnapshot.fetched_at.desc(), PageSnapshot.id.desc())
    ).first()

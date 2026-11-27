"""The discovery job: check every source, extract what changed (FR-D7).

Run by `scholar discover` (and later by the daily schedule, Phase 8) or by
"Run now" in the app. One failing source never stops the others: its error
is recorded, the run continues, and the run's status becomes "partial".
"""

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.modules.fetcher.fetcher import PoliteFetcher
from app.modules.jobs.models import JobRun
from app.modules.scholarships import service as scholarships
from app.modules.sources import service as sources
from app.modules.sources.models import Source, SourceStatus

log = logging.getLogger(__name__)

DISCOVER = "discover"


@dataclass
class SourceOutcome:
    """What happened to one source in this run."""

    source_id: int
    url: str
    check: str  # a FetchStatus value, "skipped" or "error"
    changed: bool = False
    extraction: str | None = None  # an ExtractionStatus value, if it ran
    message: str = ""


@dataclass
class DiscoveryReport:
    """The whole run, stored as the job run's summary."""

    sources: list[SourceOutcome] = field(default_factory=list)
    scholarships_created: int = 0
    scholarships_updated: int = 0
    criteria_rejected: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: int = 0

    def as_summary(self) -> dict[str, Any]:
        return asdict(self)


def run_discovery(  # pylint: disable=too-many-arguments
    session: Session,
    *,
    user_id: int,
    fetcher: PoliteFetcher,
    provider: AIProvider,
    trigger: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> JobRun:
    """Check and extract every approved source. Commits after each source."""
    run = JobRun(
        user_id=user_id,
        kind=DISCOVER,
        trigger=trigger,
        status="running",
        started_at=clock(),
        summary={},
    )
    session.add(run)
    session.commit()

    report = DiscoveryReport()
    try:
        for source in _approved_sources(session, user_id):
            report.sources.append(
                _one_source(session, fetcher, provider, source, report)
            )
            session.commit()  # each source's results are kept even if a later one fails
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Unexpected: record it so the Today screen can show it, then re-raise.
        session.rollback()
        run.status, run.error = "failed", f"{type(exc).__name__}: {exc}"[:2000]
        run.finished_at, run.summary = clock(), report.as_summary()
        session.commit()
        raise
    run.status = "partial" if report.errors else "succeeded"
    run.finished_at, run.summary = clock(), report.as_summary()
    session.commit()
    return run


def _approved_sources(session: Session, user_id: int) -> list[Source]:
    return list(
        session.scalars(
            select(Source)
            .where(Source.user_id == user_id, Source.status == SourceStatus.APPROVED)
            .order_by(Source.id)
        )
    )


def _one_source(
    session: Session,
    fetcher: PoliteFetcher,
    provider: AIProvider,
    source: Source,
    report: DiscoveryReport,
) -> SourceOutcome:
    outcome = SourceOutcome(source.id, source.url, check="error")
    try:
        checked = sources.check_source(session, fetcher, source.user_id, source.id)
        if checked.skipped:
            outcome.check = "skipped"
            outcome.message = source.last_message or "Skipped: needs your attention."
            return outcome
        outcome.check = source.last_result or "error"
        outcome.changed = checked.changed
        outcome.message = source.last_message or ""
        if checked.snapshot is not None and checked.changed:
            extraction = scholarships.extract_snapshot(
                session, provider, checked.snapshot
            )
            outcome.extraction = extraction.status.value
            outcome.message = extraction.message
            report.scholarships_created += extraction.created
            report.scholarships_updated += extraction.updated
            report.criteria_rejected += extraction.criteria_rejected
            report.input_tokens += extraction.input_tokens
            report.output_tokens += extraction.output_tokens
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # One bad source must not stop the run; record it and move on.
        session.rollback()
        log.exception("Discovery failed for source %s", source.id)
        report.errors += 1
        outcome.check = "error"
        outcome.message = f"Unexpected error: {type(exc).__name__}"
    return outcome


def latest_run(session: Session, user_id: int, kind: str = DISCOVER) -> JobRun | None:
    return session.scalars(
        select(JobRun)
        .where(JobRun.user_id == user_id, JobRun.kind == kind)
        .order_by(JobRun.started_at.desc(), JobRun.id.desc())
    ).first()

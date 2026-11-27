"""The daily job (FR-N1): discovery, then notifications.

Run by launchd as `scholar daily --scheduled` (default 07:00, and on wake if
the Mac was asleep), by `scholar daily` by hand, or by "Run now" in the app.

FR-N2: a *scheduled* run does nothing while background running is switched
off. A manual run always works, so the student can still refresh on demand.

If discovery fails, notifications are still generated from what's already
stored: a broken website mustn't hide a deadline reminder.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.modules.fetcher.fetcher import PoliteFetcher
from app.modules.jobs.discovery import run_discovery
from app.modules.jobs.models import JobRun
from app.modules.notify import service as notify
from app.modules.settings import service as settings

log = logging.getLogger(__name__)

SCHEDULE = "schedule"
BACKGROUND_OFF = "Background running is switched off; nothing was done."


@dataclass(frozen=True)
class DailyResult:
    """What the daily job did (or why it did nothing)."""

    skipped: str | None = None
    run: JobRun | None = None
    notifications: int = 0

    @property
    def ok(self) -> bool:
        return self.skipped is not None or (
            self.run is not None and self.run.status == "succeeded"
        )


def run_daily(  # pylint: disable=too-many-arguments
    session: Session,
    *,
    user_id: int,
    fetcher: PoliteFetcher,
    provider: AIProvider,
    trigger: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> DailyResult:
    if (
        trigger == SCHEDULE
        and not settings.get_settings(session, user_id).background_enabled
    ):
        session.commit()  # the settings row may have just been created
        return DailyResult(skipped=BACKGROUND_OFF)

    run: JobRun | None = None
    try:
        run = run_discovery(
            session,
            user_id=user_id,
            fetcher=fetcher,
            provider=provider,
            trigger=trigger,
            clock=clock,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        # Already recorded on the job run by run_discovery; keep going.
        log.exception("Discovery failed; generating notifications anyway")
        session.rollback()

    now = clock()
    created = notify.generate(session, user_id, today=now.date(), now=now)
    if run is not None:
        run.summary = {**run.summary, "notifications_created": len(created)}
    session.commit()
    return DailyResult(run=run, notifications=len(created))

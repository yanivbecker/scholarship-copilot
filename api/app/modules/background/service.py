"""Switch background running on and off, and report its state (FR-N2).

Two things must agree: the launchd agent (does anything get started?) and
the `background_enabled` flag (does a scheduled run do anything?). Turning
off saves the flag first, so even if unloading fails, scheduled runs do
nothing. Turning on installs first, so a failed install never claims "on".
"""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_data_dir, get_settings
from app.modules.background.launchd import (
    DEFAULT_HOUR,
    Agent,
    DryRunLaunchctl,
    RealLaunchctl,
)
from app.modules.jobs.daily import SCHEDULE
from app.modules.jobs.models import JobRun
from app.modules.settings import service as settings

SCHEDULE_TEXT = (
    f"Every day at {DEFAULT_HOUR:02d}:00, or when your Mac wakes if it was asleep."
)


def get_agent() -> Agent:
    """The real agent, or a dry run (setting, or always when under pytest)."""
    data_dir = get_data_dir()
    if get_settings().background_dry_run or "PYTEST_CURRENT_TEST" in os.environ:
        agents_dir = data_dir / "launchd-dry-run"
        plist = agents_dir / "com.scholarshipcopilot.daily.plist"
        return Agent(agents_dir, DryRunLaunchctl(loaded=plist.exists()), data_dir)
    return Agent(Path.home() / "Library" / "LaunchAgents", RealLaunchctl(), data_dir)


@dataclass(frozen=True)
class BackgroundStatus:
    """Everything the Settings page and `scholar background status` show."""

    enabled: bool
    installed: bool
    loaded: bool
    dry_run: bool
    schedule: str
    plist_path: str
    last_scheduled_run: JobRun | None

    @property
    def summary(self) -> str:
        if self.enabled and self.loaded:
            return "On: " + self.schedule
        if self.enabled and not self.loaded:
            return "Not installed: run `scholar background on` to start it."
        return "Off: nothing runs in the background. Run now still works."


def status(session: Session, user_id: int, agent: Agent) -> BackgroundStatus:
    last = session.scalars(
        select(JobRun)
        .where(JobRun.user_id == user_id, JobRun.trigger == SCHEDULE)
        .order_by(JobRun.started_at.desc(), JobRun.id.desc())
    ).first()
    return BackgroundStatus(
        enabled=settings.get_settings(session, user_id).background_enabled,
        installed=agent.installed(),
        loaded=agent.launchctl.is_loaded(),
        dry_run=isinstance(agent.launchctl, DryRunLaunchctl),
        schedule=SCHEDULE_TEXT,
        plist_path=str(agent.plist_path),
        last_scheduled_run=last,
    )


def switch(session: Session, user_id: int, agent: Agent, *, on: bool) -> None:
    """Commits the flag at the safe moment (see the module docstring)."""
    if on:
        agent.install()
        settings.set_background(session, user_id, True)
        session.commit()
    else:
        settings.set_background(session, user_id, False)
        session.commit()
        agent.remove()

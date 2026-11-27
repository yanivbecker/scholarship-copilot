"""The background switch (FR-N1, FR-N2). launchd is always faked here."""

import io
import plistlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.cli import run as cli_run
from app.modules.background import service as background
from app.modules.background.launchd import (
    API_DIR,
    LABEL,
    Agent,
    BackgroundError,
    DryRunLaunchctl,
    RealLaunchctl,
    build_plist,
)
from app.modules.jobs.models import JobRun
from app.modules.settings import service as user_settings
from app.modules.users.models import User

FAKE_UV = "/opt/fake/bin/uv"


def agent_in(tmp_path: Path, launchctl: Any = None) -> Agent:
    return Agent(
        tmp_path / "LaunchAgents",
        launchctl or DryRunLaunchctl(),
        tmp_path / "data",
        find_uv=lambda: FAKE_UV,
    )


def cli(session: Session, agent: Agent, action: str) -> tuple[int, str]:
    out = io.StringIO()
    code = cli_run(
        ["background", action],
        session_factory=lambda: Session(session.get_bind()),
        agent=agent,
        out=out,
    )
    return code, out.getvalue()


def enabled(session: Session, owner: User) -> bool:
    session.expire_all()
    return user_settings.get_settings(session, owner.id).background_enabled


def test_the_plist_runs_daily_quietly_at_seven(tmp_path: Path) -> None:
    plist = build_plist(uv=Path(FAKE_UV), api_dir=API_DIR, data_dir=tmp_path)

    assert plist["Label"] == LABEL
    assert plist["ProgramArguments"][-3:] == ["scholar", "daily", "--scheduled"]
    assert plist["WorkingDirectory"] == str(API_DIR)  # api/.env is read from here
    assert plist["StartCalendarInterval"] == {"Hour": 7, "Minute": 0}
    assert plist["RunAtLoad"] is False
    assert plist["ProcessType"] == "Background" and plist["Nice"] > 0
    assert plist["StandardOutPath"].startswith(str(tmp_path))  # logs not in repo


def test_no_secrets_are_written_into_the_plist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-not-a-real-key")
    agent = agent_in(tmp_path)

    written = agent.install().read_bytes()

    assert b"not-a-real-key" not in written
    assert set(plistlib.loads(written)["EnvironmentVariables"]) == {
        "SCHOLARSHIP_DATA_DIR"
    }


def test_on_installs_and_loads(session: Session, owner: User, tmp_path: Path) -> None:
    user_settings.set_background(session, owner.id, False)
    session.commit()
    launchctl = DryRunLaunchctl()
    agent = agent_in(tmp_path, launchctl)

    code, text = cli(session, agent, "on")

    assert code == 0 and text.startswith("On: Every day at 07:00")
    assert agent.plist_path.exists()
    assert plistlib.loads(agent.plist_path.read_bytes())["Label"] == LABEL
    assert launchctl.calls == [f"bootstrap {agent.plist_path}"]
    assert enabled(session, owner)


def test_on_again_reloads_the_new_file(
    session: Session, owner: User, tmp_path: Path
) -> None:
    del owner
    launchctl = DryRunLaunchctl()
    agent = agent_in(tmp_path, launchctl)
    cli(session, agent, "on")

    cli(session, agent, "on")

    assert launchctl.calls[1:] == ["bootout", f"bootstrap {agent.plist_path}"]


def test_off_unloads_and_removes_the_file(
    session: Session, owner: User, tmp_path: Path
) -> None:
    launchctl = DryRunLaunchctl()
    agent = agent_in(tmp_path, launchctl)
    cli(session, agent, "on")

    code, text = cli(session, agent, "off")

    assert code == 0 and text.startswith("Off: nothing runs in the background")
    assert not agent.plist_path.exists()  # or launchd loads it again at login
    assert launchctl.calls[-1] == "bootout"
    assert not enabled(session, owner)


class BrokenLaunchctl(DryRunLaunchctl):
    """launchctl that fails to unload, as it can for real."""

    def bootout(self) -> None:
        raise BackgroundError("launchctl failed")


def test_off_is_saved_even_if_unloading_fails(
    session: Session, owner: User, tmp_path: Path
) -> None:
    agent = agent_in(tmp_path, BrokenLaunchctl(loaded=True))

    code, text = cli(session, agent, "off")

    assert code == 1 and "launchctl failed" in text
    assert not enabled(session, owner)  # scheduled runs now do nothing anyway


def test_a_failed_install_does_not_claim_to_be_on(
    session: Session, owner: User, tmp_path: Path
) -> None:
    user_settings.set_background(session, owner.id, False)
    session.commit()
    agent = Agent(
        tmp_path / "LaunchAgents", DryRunLaunchctl(), tmp_path / "data", lambda: None
    )

    code, text = cli(session, agent, "on")

    assert code == 1 and "Couldn't find `uv`" in text
    assert not agent.plist_path.exists() and not enabled(session, owner)


def test_status_shows_the_last_scheduled_run(
    session: Session, owner: User, tmp_path: Path
) -> None:
    session.add(
        JobRun(
            user_id=owner.id,
            kind="discover",
            trigger="schedule",
            status="succeeded",
            started_at=datetime(2027, 1, 5, 7, tzinfo=UTC),
            summary={},
        )
    )
    session.commit()

    _, text = cli(session, agent_in(tmp_path), "status")

    assert "last scheduled run: 2027-01-05 07:00 (succeeded)" in text
    assert "dry run" in text


def test_real_launchctl_commands(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        code = 5 if args[1] == "bootstrap" else 0
        return subprocess.CompletedProcess(args, code, "", "Bootstrap failed: 5")

    launchctl = RealLaunchctl(run=fake_run)
    with pytest.raises(BackgroundError, match="Bootstrap failed"):
        launchctl.bootstrap(tmp_path / "x.plist")
    launchctl.bootout()
    assert launchctl.is_loaded()

    domain = calls[0][2]
    assert domain.startswith("gui/")
    assert calls == [
        ["/bin/launchctl", "bootstrap", domain, str(tmp_path / "x.plist")],
        ["/bin/launchctl", "bootout", f"{domain}/{LABEL}"],
        ["/bin/launchctl", "print", f"{domain}/{LABEL}"],
    ]


def test_tests_can_never_reach_the_real_launchd() -> None:
    assert isinstance(background.get_agent().launchctl, DryRunLaunchctl)


def test_settings_page_switch(client: TestClient) -> None:
    before = client.get("/api/v1/background").json()
    on = client.put("/api/v1/background", json={"enabled": True}).json()
    off = client.put("/api/v1/background", json={"enabled": False}).json()

    assert before["enabled"] is True and before["loaded"] is False
    assert before["summary"].startswith("Not installed")
    assert on["loaded"] is True and on["installed"] is True and on["dry_run"]
    assert off["enabled"] is False and off["installed"] is False

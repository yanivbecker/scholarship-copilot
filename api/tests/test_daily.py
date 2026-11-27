"""The daily job: discovery, then notifications (FR-N1, FR-N2). Fictional data."""

import io
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.cli import run as cli_run
from app.modules.jobs.daily import run_daily
from app.modules.jobs.models import JobRun
from app.modules.notify.models import Notification
from app.modules.settings import service as user_settings
from app.modules.sources import service as sources
from app.modules.users.models import User
from tests.fake_web import FakeWeb
from tests.fakes import ScriptedProvider
from tests.sample_listing import PAGE, answer, award


@pytest.fixture(name="sites")
def fixture_sites(web: FakeWeb, session: Session, owner: User) -> FakeWeb:
    web.pages[("example.org", "/awards")] = httpx2.Response(
        200, text=PAGE, headers={"content-type": "text/plain"}
    )
    sources.add_source(session, owner.id, url="https://example.org/awards")
    session.commit()
    return web


def daily(
    session: Session, sites: FakeWeb, *args: str, provider: Any = None
) -> tuple[int, str]:
    out = io.StringIO()
    code = cli_run(
        ["daily", *args],
        session_factory=lambda: Session(session.get_bind()),
        fetcher=sites.fetcher(),
        provider=provider or ScriptedProvider(answer(award())),
        out=out,
    )
    return code, out.getvalue()


def count(session: Session, model: type[Any]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_daily_checks_sources_then_notifies_once(
    session: Session, sites: FakeWeb
) -> None:
    code, text = daily(session, sites)
    again_code, again = daily(session, sites, provider=ScriptedProvider())

    assert code == 0 and "1 new notification(s)." in text
    assert again_code == 0 and "0 new notification(s)." in again  # FR-N4
    runs = session.scalars(select(JobRun).order_by(JobRun.id)).all()
    assert [r.summary["notifications_created"] for r in runs] == [1, 0]


def test_scheduled_run_does_nothing_while_background_is_off(
    session: Session, owner: User, sites: FakeWeb
) -> None:
    user_settings.set_background(session, owner.id, False)
    session.commit()

    code, text = daily(session, sites, "--scheduled")

    assert code == 0 and "switched off" in text
    assert not sites.requests  # FR-N2: nothing at all ran
    assert count(session, JobRun) == 0 and count(session, Notification) == 0


def test_a_manual_run_works_even_with_background_off(
    session: Session, owner: User, sites: FakeWeb
) -> None:
    user_settings.set_background(session, owner.id, False)
    session.commit()

    code, text = daily(session, sites)

    assert code == 0 and "Run succeeded" in text


def test_reminders_still_arrive_when_discovery_breaks(
    session: Session, owner: User, sites: FakeWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    daily(session, sites)  # stores the scholarship (due 2027-03-01)

    def broken(*_args: Any, **_kwargs: Any) -> JobRun:
        raise RuntimeError("the network is down")

    monkeypatch.setattr("app.modules.jobs.daily.run_discovery", broken)
    result = run_daily(
        session,
        user_id=owner.id,
        fetcher=sites.fetcher(),
        provider=ScriptedProvider(),
        trigger="schedule",
        clock=lambda: datetime(2027, 2, 27, 7, tzinfo=UTC),
    )

    assert not result.ok and result.run is None
    titles = session.scalars(select(Notification.title)).all()
    assert "Due in 2 days: The Test Foundation STEM Award" in titles


@pytest.mark.usefixtures("sites")
def test_run_now_runs_the_daily_job(client: TestClient) -> None:
    provider = ScriptedProvider(answer(award()))
    client.app.dependency_overrides[get_ai_provider] = lambda: provider  # type: ignore[attr-defined]

    job = client.post("/api/v1/discovery/run").json()

    assert job["trigger"] == "api"
    assert job["summary"]["notifications_created"] == 1
    assert client.get("/api/v1/notifications").json()["unread"] == 1

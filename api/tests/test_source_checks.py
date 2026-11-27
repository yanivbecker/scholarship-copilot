"""Checking sources and storing snapshots (FR-D2, FR-D4, FR-D7).

Uses the fake web (no network). Sites and text are fictional.
"""

from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.sources import service
from app.modules.sources.models import PageSnapshot, SnapshotOrigin
from app.modules.users.models import User
from tests.fake_web import FakeWeb, html

T0 = datetime(2027, 1, 10, 8, 0, tzinfo=UTC)


def add(session: Session, owner: User, url: str = "https://example.org/awards") -> int:
    source = service.add_source(session, owner.id, url=url)
    session.commit()
    return source.id


def check(  # pylint: disable=too-many-arguments
    session: Session,
    web: FakeWeb,
    owner: User,
    source_id: int,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> service.CheckOutcome:
    outcome = service.check_source(
        session, web.fetcher(), owner.id, source_id, force=force, now=now
    )
    session.commit()
    return outcome


def snapshot_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(PageSnapshot)) or 0


def test_first_check_stores_a_changed_snapshot(
    session: Session, owner: User, web: FakeWeb
) -> None:
    web.pages[("example.org", "/awards")] = html(headers={"etag": '"v1"'})
    source_id = add(session, owner)

    outcome = check(session, web, owner, source_id, now=T0)

    assert outcome.changed is True
    assert outcome.snapshot is not None
    assert outcome.snapshot.origin is SnapshotOrigin.FETCHED
    assert "GPA of 3.0 or higher." in outcome.snapshot.text
    source = outcome.source
    assert source.last_result == "ok"
    assert source.last_checked_at == T0 and source.last_changed_at == T0
    assert source.etag == '"v1"'


def test_same_text_is_not_marked_changed(
    session: Session, owner: User, web: FakeWeb
) -> None:
    web.pages[("example.org", "/awards")] = html()
    source_id = add(session, owner)
    check(session, web, owner, source_id, now=T0)

    second = check(session, web, owner, source_id, now=T0 + timedelta(days=1))

    assert second.changed is False
    assert second.source.last_changed_at == T0  # FR-D7: nothing new to extract


def test_new_text_is_marked_changed(
    session: Session, owner: User, web: FakeWeb
) -> None:
    web.pages[("example.org", "/awards")] = html()
    source_id = add(session, owner)
    check(session, web, owner, source_id, now=T0)
    web.pages[("example.org", "/awards")] = html(b"<p>New deadline: April 1</p>")

    later = T0 + timedelta(days=2)
    outcome = check(session, web, owner, source_id, now=later)

    assert outcome.changed is True
    assert outcome.source.last_changed_at == later


def test_validators_are_sent_and_304_stores_nothing(
    session: Session, owner: User, web: FakeWeb
) -> None:
    web.pages[("example.org", "/awards")] = html(headers={"etag": '"v1"'})
    source_id = add(session, owner)
    check(session, web, owner, source_id, now=T0)
    web.pages[("example.org", "/awards")] = httpx2.Response(304)

    outcome = check(session, web, owner, source_id, now=T0 + timedelta(days=1))

    assert web.requests[-1].headers["if-none-match"] == '"v1"'
    assert outcome.source.last_result == "not_modified"
    assert outcome.snapshot is None
    assert snapshot_count(session) == 1


def test_login_wall_is_skipped_later_unless_forced(
    session: Session, owner: User, web: FakeWeb
) -> None:
    web.pages[("example.org", "/awards")] = httpx2.Response(401)
    source_id = add(session, owner)
    check(session, web, owner, source_id)
    requests_so_far = len(web.requests)

    automatic = check(session, web, owner, source_id)
    assert automatic.skipped is True
    assert len(web.requests) == requests_so_far  # FR-D4: not crawled again

    forced = check(session, web, owner, source_id, force=True)
    assert forced.skipped is False
    assert forced.source.last_result == "login_required"


def test_only_the_newest_snapshots_are_kept(
    session: Session, owner: User, web: FakeWeb
) -> None:
    source_id = add(session, owner)
    for day in range(service.KEEP_SNAPSHOTS + 3):
        web.pages[("example.org", "/awards")] = html(f"<p>Version {day}</p>".encode())
        check(session, web, owner, source_id, now=T0 + timedelta(days=day))

    assert snapshot_count(session) == service.KEEP_SNAPSHOTS
    latest = service.latest_snapshot(session, source_id)
    assert latest is not None and "Version 7" in latest.text


def test_pasted_text_is_stored_exactly(session: Session, owner: User) -> None:
    source_id = add(session, owner, "https://portal.example.org/listing")
    text = "  Test Award\n\nMust be a resident of Ohio.  "

    outcome = service.paste_source_text(session, owner.id, source_id, text, now=T0)

    assert outcome.snapshot is not None
    assert outcome.snapshot.text == text
    assert outcome.snapshot.origin is SnapshotOrigin.PASTED
    assert outcome.source.last_result == "pasted"


@pytest.mark.parametrize("text", ["", "   \n ", "x" * (service.MAX_PASTE_CHARS + 1)])
def test_bad_paste_is_refused(session: Session, owner: User, text: str) -> None:
    source_id = add(session, owner)

    with pytest.raises(service.PasteError):
        service.paste_source_text(session, owner.id, source_id, text)


def test_other_users_sources_cannot_be_checked(
    session: Session, owner: User, web: FakeWeb
) -> None:
    other = User(display_name="Other Test User")
    session.add(other)
    session.flush()
    source_id = service.add_source(session, other.id, url="https://example.org/x").id

    with pytest.raises(service.SourceNotFoundError):
        service.check_source(session, web.fetcher(), owner.id, source_id)


# --- API ---------------------------------------------------------------------


def test_api_check_paste_and_snapshot(client: TestClient, web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = html()
    source = client.post(
        "/api/v1/sources", json={"url": "https://example.org/awards"}
    ).json()

    checked = client.post(f"/api/v1/sources/{source['id']}/check").json()
    assert checked["changed"] is True
    assert checked["source"]["last_result"] == "ok"
    assert checked["source"]["last_checked_at"].endswith(("+00:00", "Z"))  # UTC-aware

    snapshot = client.get(f"/api/v1/sources/{source['id']}/snapshot").json()
    assert "GPA of 3.0 or higher." in snapshot["text"]

    pasted = client.post(
        f"/api/v1/sources/{source['id']}/paste", json={"text": "Pasted listing"}
    ).json()
    assert pasted["source"]["last_result"] == "pasted"
    assert client.get(f"/api/v1/sources/{source['id']}/snapshot").json()["text"] == (
        "Pasted listing"
    )


def test_api_check_now_retries_a_login_wall(client: TestClient, web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = httpx2.Response(401)
    source = client.post(
        "/api/v1/sources", json={"url": "https://example.org/awards"}
    ).json()
    client.post(f"/api/v1/sources/{source['id']}/check")
    web.pages[("example.org", "/awards")] = html()  # the site opened up

    checked = client.post(f"/api/v1/sources/{source['id']}/check").json()

    assert checked["source"]["last_result"] == "ok"


def test_api_empty_paste_is_422(client: TestClient) -> None:
    source = client.post(
        "/api/v1/sources", json={"url": "https://example.org/a"}
    ).json()

    response = client.post(f"/api/v1/sources/{source['id']}/paste", json={"text": " "})

    assert response.status_code == 422
    assert response.json()["detail"] == "Paste the listing text first."


def test_api_snapshot_is_null_before_any_check(client: TestClient) -> None:
    source = client.post(
        "/api/v1/sources", json={"url": "https://example.org/a"}
    ).json()

    assert client.get(f"/api/v1/sources/{source['id']}/snapshot").json() is None

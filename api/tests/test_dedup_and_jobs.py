"""Duplicate detection (FR-D6) and the discovery job (FR-D7, FR-N2 "Run now").

Fake web + scripted AI; every site and scholarship is fictional.
"""

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
from app.modules.jobs.discovery import latest_run, run_discovery
from app.modules.scholarships import merge, service
from app.modules.scholarships.dedup import (
    Candidate,
    is_same_scholarship,
    name_key,
    possible_duplicate_score,
)
from app.modules.scholarships.models import Scholarship
from app.modules.sources import service as sources
from app.modules.users.models import User
from tests.fake_web import FakeWeb
from tests.fakes import ScriptedProvider
from tests.sample_listing import PAGE, answer, award

NOW = datetime(2027, 1, 15, 9, 0, tzinfo=UTC)


def plain(text: str) -> httpx2.Response:
    return httpx2.Response(200, text=text, headers={"content-type": "text/plain"})


# --- Matching rules -----------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (
            ("The Test Foundation STEM Award", "Test Foundation", None),
            ("Test Foundation STEM Scholarship", "Test Foundation", None),
            "same",
        ),
        (
            ("Smith Family Scholarship", None, None),
            ("Smith Family Memorial Scholarship", None, None),
            "possible",
        ),
        (
            ("Jones Nursing Scholarship", "Jones Fund", None),
            ("Jones Engineering Scholarship", "Jones Fund", None),
            "different",
        ),
        (
            ("STEM Award", "Acme Corp", None),
            ("STEM Award", "Beta University", None),
            "different",
        ),
        (("STEM Award", None, None), ("STEM Nursing Award", None, None), "different"),
        (
            ("Rivera Award", None, "https://ex.org/r"),
            ("The Rivera Memorial Award", None, "https://ex.org/r"),
            "same",
        ),
        (
            # Same page, unrelated names: two scholarships listed together.
            ("Rivera Award", None, "https://ex.org/list"),
            ("Kim Nursing Grant", None, "https://ex.org/list"),
            "different",
        ),
        (
            ("Women in Engineering Award", None, None),
            ("Women in Science Award", None, None),
            "different",
        ),
    ],
)
def test_matching_rules(a: tuple[Any, ...], b: tuple[Any, ...], expected: str) -> None:
    first, second = Candidate(*a), Candidate(*b)
    if is_same_scholarship(first, second):
        got = "same"
    elif possible_duplicate_score(first, second) is not None:
        got = "possible"
    else:
        got = "different"

    assert got == expected


def test_name_key_drops_generic_words() -> None:
    assert (
        name_key("The Test Foundation STEM Scholarship Program")
        == "test foundation stem"
    )


# --- Merging on save and by hand ---------------------------------------------


def extract(
    session: Session, owner: User, url: str, text: str, ai_answer: dict[str, Any]
) -> None:
    source = sources.add_source(session, owner.id, url=url)
    outcome = sources.paste_source_text(session, owner.id, source.id, text, now=NOW)
    assert outcome.snapshot is not None
    service.extract_snapshot(
        session, ScriptedProvider(ai_answer), outcome.snapshot, now=NOW
    )
    session.commit()


def count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Scholarship)) or 0


def test_same_scholarship_from_another_page_is_merged_on_save(
    session: Session, owner: User
) -> None:
    extract(session, owner, "https://example.org/awards", PAGE, answer(award()))
    other_page = PAGE.replace(
        "The Test Foundation STEM Award", "Test Foundation STEM Scholarship"
    )

    extract(
        session,
        owner,
        "https://college.example.edu/aid",
        other_page,
        answer(award(name="Test Foundation STEM Scholarship")),
    )

    assert count(session) == 1
    [scholarship] = service.list_scholarships(session, owner.id)
    assert (
        scholarship.cycles[0].source_url == "https://college.example.edu/aid"
    )  # newest source wins


def test_different_sponsors_are_not_merged(session: Session, owner: User) -> None:
    extract(session, owner, "https://example.org/awards", PAGE, answer(award()))

    extract(
        session,
        owner,
        "https://other.example.org/awards",
        PAGE,
        answer(award(sponsor="A Different Foundation")),
    )

    assert count(session) == 2


def test_possible_duplicates_can_be_merged_by_hand(
    session: Session, owner: User
) -> None:
    page = PAGE + "\nThe Test Foundation STEM Memorial Award\n"
    extract(session, owner, "https://example.org/awards", page, answer(award()))
    extract(
        session,
        owner,
        "https://example.org/memorial",
        page,
        answer(
            award(
                name="The Test Foundation STEM Memorial Award",
                cycle_year=2028,
                deadline=None,
                deadline_quote=None,
            )
        ),
    )
    [pair] = merge.possible_duplicates(session, owner.id)

    kept = merge.merge_scholarships(session, owner.id, pair.first.id, pair.second.id)
    session.commit()

    assert count(session) == 1
    assert sorted(c.year for c in kept.cycles) == [2027, 2028]  # both years kept


def test_merging_a_scholarship_with_itself_is_refused(
    session: Session, owner: User
) -> None:
    extract(session, owner, "https://example.org/awards", PAGE, answer(award()))
    [scholarship] = service.list_scholarships(session, owner.id)

    with pytest.raises(merge.MergeError):
        merge.merge_scholarships(session, owner.id, scholarship.id, scholarship.id)


# --- The discovery job ---------------------------------------------------------


@pytest.fixture(name="sites")
def fixture_sites(web: FakeWeb) -> FakeWeb:
    web.pages[("example.org", "/awards")] = plain(PAGE)
    web.pages[("example.org", "/portal")] = httpx2.Response(401)
    return web


def add_sources(session: Session, owner: User) -> None:
    for url in ("https://example.org/awards", "https://example.org/portal"):
        sources.add_source(session, owner.id, url=url)
    session.commit()


def test_discovery_checks_every_source_and_extracts_changes(
    session: Session, owner: User, sites: FakeWeb
) -> None:
    add_sources(session, owner)
    provider = ScriptedProvider(answer(award()))

    job = run_discovery(
        session,
        user_id=owner.id,
        fetcher=sites.fetcher(),
        provider=provider,
        trigger="cli",
    )

    assert job.status == "succeeded"
    checks = {s["url"]: (s["check"], s["extraction"]) for s in job.summary["sources"]}
    assert checks == {
        "https://example.org/awards": ("ok", "done"),
        "https://example.org/portal": ("login_required", None),  # FR-D4: not extracted
    }
    assert job.summary["scholarships_created"] == 1
    assert job.finished_at is not None


def test_second_run_skips_unchanged_pages_and_dead_ends(
    session: Session, owner: User, sites: FakeWeb
) -> None:
    add_sources(session, owner)
    run_discovery(
        session,
        user_id=owner.id,
        fetcher=sites.fetcher(),
        provider=ScriptedProvider(answer(award())),
        trigger="cli",
    )
    provider = ScriptedProvider()  # any AI call would fail: there are no answers

    job = run_discovery(
        session,
        user_id=owner.id,
        fetcher=sites.fetcher(),
        provider=provider,
        trigger="cli",
    )

    assert not provider.prompts  # FR-D7: same text, no extraction, no cost
    checks = {s["url"]: s["check"] for s in job.summary["sources"]}
    assert checks["https://example.org/portal"] == "skipped"
    assert latest_run(session, owner.id) == job


def test_one_broken_source_does_not_stop_the_run(
    session: Session, owner: User, sites: FakeWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_sources(session, owner)
    sites.pages[("example.org", "/third")] = plain(PAGE)
    sources.add_source(session, owner.id, url="https://example.org/third")
    session.commit()
    calls = {"n": 0}
    real = service.extract_snapshot

    def flaky(*args: Any, **kwargs: Any) -> service.ExtractionReport:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(
        "app.modules.jobs.discovery.scholarships.extract_snapshot", flaky
    )

    job = run_discovery(
        session,
        user_id=owner.id,
        fetcher=sites.fetcher(),
        provider=ScriptedProvider(answer(award())),
        trigger="cli",
    )

    assert job.status == "partial"
    assert job.summary["errors"] == 1
    outcomes = [s["check"] for s in job.summary["sources"]]
    assert outcomes == ["error", "login_required", "ok"]  # the run kept going


def test_cli_discover(session: Session, owner: User, sites: FakeWeb) -> None:
    add_sources(session, owner)
    out = io.StringIO()

    code = cli_run(
        ["discover"],
        session_factory=lambda: Session(session.get_bind()),
        fetcher=sites.fetcher(),
        provider=ScriptedProvider(answer(award())),
        out=out,
    )

    assert code == 0
    text = out.getvalue()
    assert "login_required" in text and "https://example.org/portal" in text
    assert "Run succeeded: 2 sources checked, 1 new" in text


# --- API -----------------------------------------------------------------------


@pytest.mark.usefixtures("sites")
def test_api_run_now_and_latest(client: TestClient) -> None:
    provider = ScriptedProvider(answer(award()))
    client.app.dependency_overrides[get_ai_provider] = lambda: provider  # type: ignore[attr-defined]
    assert client.get("/api/v1/discovery/runs/latest").json() is None
    client.post("/api/v1/sources", json={"url": "https://example.org/awards"})

    job = client.post("/api/v1/discovery/run").json()

    assert job["status"] == "succeeded" and job["trigger"] == "api"
    latest = client.get("/api/v1/discovery/runs/latest").json()
    assert latest["id"] == job["id"]
    assert latest["summary"]["scholarships_created"] == 1


def test_api_duplicates_and_merge(client: TestClient) -> None:
    page = PAGE + "\nThe Test Foundation STEM Memorial Award\n"
    answers = [
        answer(award()),
        answer(
            award(
                name="The Test Foundation STEM Memorial Award",
                cycle_year=2028,
                deadline=None,
                deadline_quote=None,
            )
        ),
    ]
    for path, ai_answer in zip(("/a", "/b"), answers, strict=True):
        provider = ScriptedProvider(ai_answer)
        client.app.dependency_overrides[get_ai_provider] = lambda p=provider: p  # type: ignore[attr-defined]
        source = client.post(
            "/api/v1/sources", json={"url": f"https://example.org{path}"}
        ).json()
        client.post(f"/api/v1/sources/{source['id']}/paste", json={"text": page})
        client.post(f"/api/v1/sources/{source['id']}/extract")

    [pair] = client.get("/api/v1/scholarships/duplicates").json()
    merged = client.post(
        f"/api/v1/scholarships/{pair['first_id']}/merge",
        json={"other_id": pair["second_id"]},
    ).json()

    assert [c["year"] for c in merged["cycles"]] == [2028, 2027]
    assert len(client.get("/api/v1/scholarships").json()) == 1
    assert client.get("/api/v1/scholarships/duplicates").json() == []

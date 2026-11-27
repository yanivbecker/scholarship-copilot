"""Weekly source search (FR-N3, FR-D1). No real search service is called."""

import io
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli import run as cli_run
from app.core.config import Settings
from app.modules.settings import service as user_settings
from app.modules.sources import service as sources
from app.modules.sources.models import Source, SourceStatus
from app.modules.sources.search import (
    MAX_NEW_PER_RUN,
    SearchError,
    SearchHit,
    TavilySearcher,
    build_searcher,
    run_search,
    search_due,
)
from app.modules.users.models import User
from tests.fake_web import FakeWeb
from tests.fakes import ScriptedProvider

NOW = datetime(2027, 1, 4, 7, tzinfo=UTC)


@dataclass
class FakeSearcher:
    """Returns canned hits for every query and records the queries."""

    hits: list[SearchHit]
    queries: list[str] = field(default_factory=list)
    fail: bool = False

    def search(self, query: str) -> list[SearchHit]:
        self.queries.append(query)
        if self.fail:
            raise SearchError("The search service's limit was reached; try later.")
        return self.hits


def save_queries(session: Session, owner: User, *queries: str) -> None:
    user_settings.set_search_queries(session, owner.id, list(queries))
    session.commit()


def statuses(session: Session) -> dict[str, SourceStatus]:
    return {s.url: s.status for s in session.scalars(select(Source))}


def test_tavily_request_carries_only_the_query() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200,
            json={
                "results": [
                    {"url": "https://example.org/a", "title": "A", "content": "..."},
                    {"title": "no url"},
                ]
            },
        )

    searcher = TavilySearcher(
        "tvly-test", httpx2.Client(transport=httpx2.MockTransport(handler))
    )

    hits = searcher.search("nursing scholarship OH")

    assert hits == [SearchHit("https://example.org/a", "A")]
    assert len(seen) == 1
    request = seen[0]
    assert request.url == "https://api.tavily.com/search"
    assert request.headers["authorization"] == "Bearer tvly-test"
    body = json.loads(request.content)
    assert body["query"] == "nursing scholarship OH"
    assert set(body) == {"query", "max_results", "search_depth", "include_answer"}


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "was refused"), (429, "limit was reached"), (500, "answered 500")],
)
def test_tavily_errors_are_explained(status: int, message: str) -> None:
    client = httpx2.Client(
        transport=httpx2.MockTransport(lambda _r: httpx2.Response(status))
    )
    with pytest.raises(SearchError, match=message):
        TavilySearcher("tvly-test", client).search("q")


def test_results_become_pending_sources_after_safety_checks(
    session: Session, owner: User
) -> None:
    sources.add_source(session, owner.id, url="https://example.org/known")
    rejected = sources.add_source(session, owner.id, url="https://example.org/nope")
    rejected.status = SourceStatus.REJECTED
    save_queries(session, owner, "nursing scholarship")
    searcher = FakeSearcher(
        [
            SearchHit("https://example.org/new-award", "  New   Award "),
            SearchHit("https://www.fastweb.com/college-scholarships", "Aggregator"),
            SearchHit("http://127.0.0.1/admin", "Private address"),
            SearchHit("https://example.org/known", "Already added"),
            SearchHit("https://example.org/nope", "Rejected before"),
            SearchHit("https://example.org/new-award#apply", "Same page"),
        ]
    )

    report = run_search(session, owner.id, searcher, now=NOW)

    assert (report.suggested, report.blocked, report.already_known) == (1, 2, 3)
    new = session.scalars(
        select(Source).where(Source.url == "https://example.org/new-award")
    ).one()
    assert new.status is SourceStatus.PENDING_REVIEW and new.label == "New Award"
    assert statuses(session)["https://example.org/nope"] is SourceStatus.REJECTED
    assert user_settings.get_settings(session, owner.id).last_search_at == NOW


def test_one_run_suggests_a_limited_number(session: Session, owner: User) -> None:
    save_queries(session, owner, "q")
    hits = [SearchHit(f"https://example.org/p{i}", "x") for i in range(40)]

    report = run_search(session, owner.id, FakeSearcher(hits), now=NOW)

    assert report.suggested == MAX_NEW_PER_RUN


def test_search_runs_weekly_and_only_with_saved_queries(
    session: Session, owner: User
) -> None:
    row = user_settings.get_settings(session, owner.id)
    assert not search_due(row, NOW, 7)  # no queries: nothing is ever sent

    save_queries(session, owner, "q")
    assert search_due(row, NOW, 7)
    row.last_search_at = NOW - timedelta(days=6)
    assert not search_due(row, NOW, 7)
    row.last_search_at = NOW - timedelta(days=7)
    assert search_due(row, NOW, 7)


def daily(session: Session, web: FakeWeb, searcher: FakeSearcher) -> str:
    out = io.StringIO()
    cli_run(
        ["daily"],
        session_factory=lambda: Session(session.get_bind()),
        fetcher=web.fetcher(),
        provider=ScriptedProvider(),
        searcher=searcher,
        out=out,
    )
    return out.getvalue()


def test_daily_searches_once_a_week_and_never_fetches_suggestions(
    session: Session, owner: User, web: FakeWeb
) -> None:
    save_queries(session, owner, "nursing scholarship")
    searcher = FakeSearcher([SearchHit("https://example.org/suggested", "S")])

    first = daily(session, web, searcher)
    daily(session, web, searcher)

    assert "Search: 1 new page(s) to review" in first
    assert searcher.queries == ["nursing scholarship"]  # not again the same week
    assert not [r for r in web.requests if r.url.path == "/suggested"]  # FR-D1


def test_a_search_failure_does_not_stop_the_daily_job(
    session: Session, owner: User, web: FakeWeb
) -> None:
    save_queries(session, owner, "q")

    text = daily(session, web, FakeSearcher([], fail=True))

    assert "limit was reached" in text and "notification(s)" in text


def test_review_approves_or_rejects_suggestions(
    client: TestClient, session: Session, owner: User
) -> None:
    for path in ("/a", "/b"):
        session.add(
            Source(
                user_id=owner.id,
                url=f"https://example.org{path}",
                status=SourceStatus.PENDING_REVIEW,
            )
        )
    session.commit()
    a, b = session.scalars(select(Source).order_by(Source.id)).all()

    approved = client.post(f"/api/v1/sources/{a.id}/review", json={"approve": True})
    rejected = client.post(f"/api/v1/sources/{b.id}/review", json={"approve": False})
    again = client.post(f"/api/v1/sources/{a.id}/review", json={"approve": False})

    assert approved.json()["status"] == "approved"
    assert rejected.json()["status"] == "rejected"
    assert again.status_code == 422


def test_no_search_key_means_no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    assert build_searcher(Settings(_env_file=None)) is None  # type: ignore[call-arg]

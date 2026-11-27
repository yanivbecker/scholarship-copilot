"""Weekly search for new scholarship pages (FR-N3, FR-D1).

Owner decision (2026-11-27): the student writes the queries. The app only
*suggests* them, from an allowlist of facts that describe what the student
studies, not who they are. Identifying facts (name, email, phone, school,
city) and sensitive ones (citizenship, finances, demographics) are never used.
Nothing is sent until the student saves queries on the Settings page.
"""

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Protocol

import httpx2
from sqlalchemy.orm import Session

from app.core.config import Settings as AppSettings
from app.core.config import get_settings as get_app_settings

from app.modules.profile import repository as profile_repo
from app.modules.profile.catalog import choice_label
from app.modules.settings import service as settings
from app.modules.settings.models import UserSettings
from app.modules.sources import service as sources
from app.modules.sources.models import Source, SourceStatus
from app.modules.sources.url_safety import UnsafeURLError, normalize_source_url

# The only facts a suggested query may contain.
QUERY_FACTS = (
    "education_level",
    "major",
    "intended_career",
    "state_of_residence",
    "expected_graduation_year",
)


def suggest_queries(session: Session, user_id: int) -> list[str]:
    facts = {
        f.key: f.value
        for f in profile_repo.list_facts(session, user_id)
        if f.key in QUERY_FACTS
    }
    level = facts.get("education_level")
    level_text = choice_label(level).lower() if isinstance(level, str) else None
    major = facts.get("major") if isinstance(facts.get("major"), str) else None
    career = facts.get("intended_career")
    state = facts.get("state_of_residence")
    year = facts.get("expected_graduation_year")

    suggestions = []
    if major:
        suggestions.append(f"{major} scholarship" + (f" {state}" if state else ""))
    if level_text:
        suggestions.append(
            f"scholarships for {level_text} students"
            + (f" in {state}" if state else "")
        )
    if isinstance(career, str) and career:
        suggestions.append(f"{career} scholarship")
    if level_text and isinstance(year, int):
        suggestions.append(f"{level_text} scholarship class of {year}")
    if not suggestions:
        suggestions.append("undergraduate scholarship application")
    return list(dict.fromkeys(" ".join(s.split()) for s in suggestions))


# --- Running the search ---------------------------------------------------------

TAVILY_URL = "https://api.tavily.com/search"
RESULTS_PER_QUERY = 10
MAX_NEW_PER_RUN = 15


class SearchError(RuntimeError):
    """The search service failed. The message is user-facing."""


@dataclass(frozen=True)
class SearchHit:
    """One result. Title and snippet are untrusted text from the web."""

    url: str
    title: str


class Searcher(Protocol):
    """Anything that turns a query into result URLs."""

    def search(self, query: str) -> list[SearchHit]: ...


@dataclass
class TavilySearcher:
    """Tavily's REST search (POST /search, bearer key). Only the query is sent."""

    api_key: str
    client: httpx2.Client

    def search(self, query: str) -> list[SearchHit]:
        try:
            response = self.client.post(
                TAVILY_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "query": query,
                    "max_results": RESULTS_PER_QUERY,
                    "search_depth": "basic",
                    "include_answer": False,
                },
                timeout=20.0,
            )
        except httpx2.HTTPError:
            raise SearchError("Couldn't reach the search service.") from None
        if response.status_code in (401, 403):
            raise SearchError("The search key (TAVILY_API_KEY) was refused.")
        if response.status_code == 429:
            raise SearchError("The search service's limit was reached; try later.")
        if response.status_code != 200:
            raise SearchError(f"The search service answered {response.status_code}.")
        try:
            results = response.json().get("results", [])
        except ValueError:
            raise SearchError("The search service sent an unreadable answer.") from None
        return [
            SearchHit(str(r.get("url", "")), str(r.get("title", ""))[:200])
            for r in results
            if isinstance(r, dict) and r.get("url")
        ]


@dataclass
class SearchReport:
    """What one search run did (stored on the daily job run)."""

    queries: int = 0
    suggested: int = 0
    already_known: int = 0
    blocked: int = 0  # aggregators, unsafe addresses, unreadable URLs
    error: str | None = None

    def as_summary(self) -> dict[str, object]:
        return asdict(self)


def search_due(row: UserSettings, now: datetime, interval_days: int) -> bool:
    if not row.search_queries:
        return False
    return row.last_search_at is None or now - row.last_search_at >= timedelta(
        days=interval_days
    )


def run_search(
    session: Session, user_id: int, searcher: Searcher, *, now: datetime
) -> SearchReport:
    """FR-N3: new pages become *pending* sources; nothing is fetched until
    the student approves one (FR-D1). Rejected pages are never suggested again."""
    row = settings.get_settings(session, user_id)
    report = SearchReport(queries=len(row.search_queries))
    known = {s.url for s in sources.list_sources(session, user_id)}  # any status
    try:
        for query in row.search_queries:
            for hit in searcher.search(query):
                if report.suggested >= MAX_NEW_PER_RUN:
                    break
                try:
                    url = normalize_source_url(hit.url)
                except UnsafeURLError:  # aggregator, private address, bad URL
                    report.blocked += 1
                    continue
                if url in known:
                    report.already_known += 1
                    continue
                known.add(url)
                session.add(
                    Source(
                        user_id=user_id,
                        url=url,
                        label=" ".join(hit.title.split())[:200] or None,
                        status=SourceStatus.PENDING_REVIEW,
                    )
                )
                report.suggested += 1
    except SearchError as exc:
        report.error = str(exc)
    row.last_search_at = now
    session.flush()
    return report


USER_AGENT = "ScholarshipCopilot/0.1 (personal scholarship assistant)"


def build_searcher(app_settings: AppSettings) -> TavilySearcher | None:
    """None unless TAVILY_API_KEY is set (FR-N3 is optional)."""
    if app_settings.tavily_api_key is None:
        return None
    return TavilySearcher(
        app_settings.tavily_api_key.get_secret_value(),
        httpx2.Client(headers={"User-Agent": USER_AGENT}),
    )


def get_searcher() -> Iterator[Searcher | None]:
    """FastAPI dependency (no parameters: see tests/test_api_contract.py)."""
    searcher = build_searcher(get_app_settings())
    try:
        yield searcher
    finally:
        if searcher is not None:
            searcher.client.close()

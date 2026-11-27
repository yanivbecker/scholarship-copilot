"""The Today screen (FR-UI1) and table fields (FR-UI2). Fictional data.

"Now" is pinned so deadlines and the 7-day "new" window are deterministic.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.dashboard.service import today_view
from app.modules.profile import service as profile
from app.modules.profile.models import FactOrigin
from app.modules.scholarships import service as scholarships
from app.modules.scholarships.models import Scholarship
from app.modules.sources import service as sources
from app.modules.tracking.status import ApplicationStatus
from app.modules.users.models import User
from tests.fakes import ScriptedProvider
from tests.sample_listing import PAGE, answer, award

NOW = datetime(2027, 1, 15, 9, 0, tzinfo=UTC)


def add(session: Session, owner: User, name: str, **overrides: Any) -> Scholarship:
    """Extract one fictional scholarship (its name is added to the page text)."""
    text = PAGE + f"\n{name}\n"
    source = sources.add_source(
        session, owner.id, url=f"https://example.org/{len(name)}{name[:3]}"
    )
    snapshot = sources.paste_source_text(
        session, owner.id, source.id, text, now=NOW
    ).snapshot
    assert snapshot is not None
    scholarships.extract_snapshot(
        session,
        ScriptedProvider(answer(award(name=name, **overrides))),
        snapshot,
        now=NOW,
    )
    session.commit()
    return next(
        s for s in scholarships.list_scholarships(session, owner.id) if s.name == name
    )


def fact(session: Session, owner: User, key: str, value: Any) -> None:
    profile.set_fact(session, owner.id, key, value, origin=FactOrigin.MANUAL)
    session.commit()


def kinds(view: Any) -> list[str]:
    return [a.kind for a in view.actions]


def test_missing_facts_are_ranked_by_how_many_scholarships_they_unlock(
    session: Session, owner: User
) -> None:
    add(session, owner, "Alpha Test Award")
    add(session, owner, "Beta Test Award", criteria=award()["criteria"][:1])  # GPA only

    view = today_view(session, owner.id, NOW)

    fact_actions = [a for a in view.actions if a.kind == "add_fact"]
    assert fact_actions[0].fact_key == "gpa"
    assert fact_actions[0].detail == "Needed to check 2 scholarships."
    assert {a.fact_key for a in fact_actions[1:]} == {
        "state_of_residence",
        "enrollment_status",
        "education_level",
    }


def test_free_text_and_eligible_actions(session: Session, owner: User) -> None:
    alpha = add(session, owner, "Alpha Test Award")

    view = today_view(session, owner.id, NOW)
    assert "confirm_requirements" in kinds(view)

    for key, value in {
        "gpa": 3.5,
        "state_of_residence": "OH",
        "enrollment_status": "full_time",
        "education_level": "undergraduate",
    }.items():
        fact(session, owner, key, value)
    only_gpa = add(session, owner, "Beta Test Award", criteria=award()["criteria"][:1])

    view = today_view(session, owner.id, NOW)
    confirm = [a for a in view.actions if a.kind == "confirm_eligibility"]
    assert [a.scholarship_id for a in confirm] == [only_gpa.id]
    assert alpha.id not in [a.scholarship_id for a in confirm]  # still has a yes/no


def test_login_walled_sources_ask_for_a_paste(session: Session, owner: User) -> None:
    portal = sources.add_source(
        session, owner.id, url="https://portal.example.org/x", label="Portal"
    )
    portal.last_result = "login_required"
    session.commit()

    view = today_view(session, owner.id, NOW)

    [action] = [a for a in view.actions if a.kind == "paste_text"]
    assert action.detail == "Portal" and action.page == "sources"


def test_deadlines_only_open_relevant_and_within_60_days(
    session: Session, owner: User
) -> None:
    soon = add(session, owner, "Soon Test Award")  # due 2027-03-01: 45 days
    later = add(
        session,
        owner,
        "Later Test Award",
        deadline="2027-06-01",
        deadline_quote="Applications are due June 1, 2027.",
    )
    past = add(
        session,
        owner,
        "Past Test Award",
        deadline="2027-01-01",
        deadline_quote="Applications are due January 1, 2027.",
    )
    done = add(session, owner, "Done Test Award")
    done.status = ApplicationStatus.SUBMITTED.value
    session.commit()
    del later, past  # outside the window / closed: must not appear

    view = today_view(session, owner.id, NOW)

    assert [(d.name, d.days_left) for d in view.deadlines] == [("Soon Test Award", 45)]
    assert view.deadlines[0].scholarship_id == soon.id


def test_deadline_soon_for_applications_in_progress(
    session: Session, owner: User
) -> None:
    item = add(session, owner, "Soon Test Award")
    item.status = ApplicationStatus.IN_PROGRESS.value
    session.commit()

    view = today_view(session, owner.id, datetime(2027, 2, 20, 9, tzinfo=UTC))

    [action] = [a for a in view.actions if a.kind == "deadline_soon"]
    assert action.title == "Due in 9 days"


def test_new_matches_are_from_the_last_week(session: Session, owner: User) -> None:
    fresh = add(session, owner, "Fresh Test Award")
    old = add(session, owner, "Old Test Award")
    fresh.created_at = NOW - timedelta(days=2)
    old.created_at = NOW - timedelta(days=20)
    session.commit()

    view = today_view(session, owner.id, NOW)

    assert [m.name for m in view.new_matches] == ["Fresh Test Award"]


def test_counts(session: Session, owner: User) -> None:
    add(session, owner, "Alpha Test Award")
    fact(session, owner, "gpa", 2.0)  # fails the GPA minimum

    view = today_view(session, owner.id, NOW)

    assert view.counts == {"ineligible": 1, "total": 1}
    assert not view.deadlines  # ineligible ones aren't on the deadline list


# --- API ---------------------------------------------------------------------


def test_api_today_and_table_fields(client: TestClient, scholarship_id: int) -> None:
    today = client.get("/api/v1/dashboard/today").json()

    assert set(today) == {"actions", "deadlines", "new_matches", "counts", "last_run"}
    assert today["counts"]["total"] == 1
    [row] = client.get("/api/v1/eligibility").json()
    assert row["scholarship_id"] == scholarship_id
    assert (row["status"], row["status_label"]) == ("discovered", "Discovered")
    assert (row["amount"], row["amount_text"]) == (2500, "$2,500")
    assert row["open_questions"] >= 1
    assert date.fromisoformat(row["deadline"]) == date(2027, 3, 1)

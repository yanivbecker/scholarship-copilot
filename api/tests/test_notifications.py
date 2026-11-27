"""Notifications: only material changes, never repeated (FR-N4, FR-N5).

The scholarship is the fictional sample award (due 2027-03-01, $2,500).
"""

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import LocalFileStorage
from app.modules.notify import service as notify
from app.modules.notify.models import Notification, WatchState
from app.modules.privacy.service import delete_all_personal_data
from app.modules.scholarships.models import Scholarship, ScholarshipCycle
from app.modules.settings.models import UserSettings
from app.modules.sources.search import suggest_queries
from app.modules.users.models import User

V1 = "/api/v1"
TODAY = date(2027, 1, 1)
NOW = datetime(2027, 1, 1, 7, tzinfo=UTC)


def run(session: Session, user: User, today: date = TODAY) -> list[str]:
    created = notify.generate(session, user.id, today=today, now=NOW)
    session.commit()
    return [n.title for n in created]


def cycle(session: Session, scholarship_id: int) -> ScholarshipCycle:
    found = session.scalars(
        select(ScholarshipCycle).where(
            ScholarshipCycle.scholarship_id == scholarship_id
        )
    ).first()
    assert found is not None
    return found


def test_a_new_match_is_announced_once(
    session: Session, scholarship_id: int, owner: User
) -> None:
    del scholarship_id
    first = run(session, owner)
    again = run(session, owner)

    assert first == ["New match: The Test Foundation STEM Award"]
    assert again == []  # FR-N4: nothing changed, nothing said


def test_a_deadline_change_is_announced_with_what_changed(
    session: Session, scholarship_id: int, owner: User
) -> None:
    run(session, owner)
    cycle(session, scholarship_id).deadline = date(2027, 3, 15)
    session.commit()

    titles = run(session, owner)
    again = run(session, owner)

    assert titles == ["Changed: The Test Foundation STEM Award"]
    [note] = session.scalars(
        select(Notification).where(Notification.kind == "changed")
    ).all()
    assert note.body == "Deadline: 2027-03-01 → 2027-03-15."
    assert again == []


def test_eligibility_changes_count_but_non_matches_stay_quiet(
    client: TestClient, session: Session, scholarship_id: int, owner: User
) -> None:
    run(session, owner)
    client.put(f"{V1}/facts/gpa", json={"value": 2.0})  # below the 3.0 minimum

    assert run(session, owner) == ["Changed: The Test Foundation STEM Award"]
    body = session.scalars(
        select(Notification.body).where(Notification.kind == "changed")
    ).one()
    assert "Eligibility: needs info → not eligible." in body

    # Still not eligible: a new amount isn't worth a message.
    cycle(session, scholarship_id).amount_text = "$3,000"
    session.commit()
    assert run(session, owner) == []


def test_deadline_reminders_fire_once_per_threshold(
    session: Session, scholarship_id: int, owner: User
) -> None:
    del scholarship_id
    due = date(2027, 3, 1)
    run(session, owner)  # the new-match message

    assert run(session, owner, due - timedelta(days=20)) == []
    assert run(session, owner, due - timedelta(days=10)) == [
        "Due in 10 days: The Test Foundation STEM Award"
    ]
    assert run(session, owner, due - timedelta(days=9)) == []
    assert run(session, owner, due - timedelta(days=1)) == [
        "Due in 1 day: The Test Foundation STEM Award"
    ]
    assert run(session, owner, due - timedelta(days=1)) == []


def test_turning_notifications_off_and_on_does_not_flood(
    client: TestClient, session: Session, scholarship_id: int, owner: User
) -> None:
    off = client.patch(f"{V1}/profile", json={"notifications_enabled": False})
    assert off.status_code == 200

    assert run(session, owner) == []
    # Watched anyway, so turning them on later doesn't announce old news.
    assert session.scalars(select(WatchState)).one().scholarship_id == scholarship_id
    assert (
        client.patch(f"{V1}/profile", json={"notifications_enabled": True}).status_code
        == 200
    )
    assert run(session, owner) == []


def test_each_kind_can_be_switched_off(
    client: TestClient, session: Session, scholarship_id: int, owner: User
) -> None:
    del scholarship_id
    response = client.put(
        f"{V1}/settings/notifications", json={"kinds": {"new_match": False}}
    )
    assert response.json()["notification_kinds"] == {
        "new_match": False,
        "changed": True,
        "deadline": True,
    }

    assert run(session, owner) == []
    assert run(session, owner, date(2027, 2, 25)) == [
        "Due in 4 days: The Test Foundation STEM Award"
    ]


def test_finished_applications_are_left_alone(
    session: Session, scholarship_id: int, owner: User
) -> None:
    run(session, owner)
    scholarship = session.get(Scholarship, scholarship_id)
    assert scholarship is not None
    scholarship.status = "submitted"
    cycle(session, scholarship_id).deadline = date(2027, 3, 15)
    session.commit()

    assert run(session, owner) == []
    assert run(session, owner, date(2027, 3, 14)) == []


def test_notifications_api_lists_and_marks_read(
    client: TestClient, session: Session, scholarship_id: int, owner: User
) -> None:
    del scholarship_id
    run(session, owner)
    run(session, owner, date(2027, 2, 27))

    body = client.get(f"{V1}/notifications").json()
    assert body["unread"] == 2
    newest = body["items"][0]
    assert newest["kind"] == "deadline" and newest["read_at"] is None

    one = client.post(f"{V1}/notifications/read", json={"ids": [newest["id"]]})
    assert one.json()["unread"] == 1
    every = client.post(f"{V1}/notifications/read", json={})
    assert every.json()["unread"] == 0
    assert client.get(f"{V1}/notifications?unread_only=true").json()["items"] == []


def test_settings_defaults_and_validation(client: TestClient) -> None:
    body = client.get(f"{V1}/settings").json()

    assert body["background_enabled"] is True
    assert body["search_queries"] == [] and body["search_configured"] is False
    assert (
        client.put(
            f"{V1}/settings/notifications", json={"kinds": {"spam": True}}
        ).status_code
        == 422
    )
    saved = client.put(
        f"{V1}/settings/search-queries",
        json={"queries": ["  nursing   scholarship ", "", "nursing scholarship"]},
    ).json()
    assert saved["search_queries"] == ["nursing scholarship"]
    too_long = client.put(
        f"{V1}/settings/search-queries", json={"queries": ["x" * 201]}
    )
    assert too_long.status_code == 422


def test_suggested_queries_use_only_allowlisted_facts(
    client: TestClient, session: Session, owner: User
) -> None:
    facts = {
        "full_name": "Sam Example",
        "school_name": "Example High",
        "city": "Exampleville",
        "gender": "nonbinary",
        "household_income": 40000,
        "major": "Nursing",
        "state_of_residence": "OH",
        "education_level": "undergraduate",
    }
    for key, value in facts.items():
        assert client.put(f"{V1}/facts/{key}", json={"value": value}).status_code == 200

    suggested = " | ".join(suggest_queries(session, owner.id))

    assert "Nursing scholarship OH" in suggested
    assert "undergraduate students in OH" in suggested
    for private in ("Sam", "Example High", "Exampleville", "nonbinary", "40000"):
        assert private not in suggested


def test_deleting_my_data_removes_notifications_and_settings(
    client: TestClient,
    session: Session,
    scholarship_id: int,
    owner: User,
    storage: LocalFileStorage,
) -> None:
    del scholarship_id
    run(session, owner)
    client.get(f"{V1}/settings")

    report = delete_all_personal_data(session, storage)

    for table in ("notifications", "watch_states", "user_settings"):
        assert table in report.rows_by_table
    assert session.scalars(select(Notification)).all() == []
    assert session.scalars(select(UserSettings)).all() == []


def test_a_scholarship_you_cannot_get_is_not_announced(
    client: TestClient, session: Session, scholarship_id: int, owner: User
) -> None:
    del scholarship_id
    client.put(f"{V1}/facts/gpa", json={"value": 2.0})  # below the 3.0 minimum

    assert run(session, owner) == []
    assert run(session, owner, date(2027, 2, 27)) == []  # no reminders either

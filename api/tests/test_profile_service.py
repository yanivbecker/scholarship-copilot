"""Profile service rules (FR-P3, FR-P4, FR-P5, FR-P6, FR-P7, NFR-8, NFR-12).

All names and values below are fictional test data (NFR-10).
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.profile import service
from app.modules.profile.catalog import FactValidationError
from app.modules.profile.models import (
    FactOrigin,
    OperatingMode,
    Profile,
    ProfileFact,
    Story,
)
from app.modules.users.models import User

Q = FactOrigin.QUESTIONNAIRE


def other_user(session: Session) -> User:
    user = User(display_name="Other Test User")
    session.add(user)
    session.flush()
    return user


# --- Profile / operating mode (FR-P7) ---------------------------------------


def test_profile_defaults_to_hybrid_mode(session: Session, owner: User) -> None:
    profile = service.get_or_create_profile(session, owner.id)

    assert profile.operating_mode is OperatingMode.HYBRID
    assert profile.onboarding_completed_at is None


def test_get_or_create_profile_is_idempotent(session: Session, owner: User) -> None:
    first = service.get_or_create_profile(session, owner.id)
    second = service.get_or_create_profile(session, owner.id)

    assert first.id == second.id


def test_operating_mode_can_change(session: Session, owner: User) -> None:
    service.set_operating_mode(session, owner.id, OperatingMode.DISCOVERY)
    session.commit()

    profile = service.get_or_create_profile(session, owner.id)
    assert profile.operating_mode is OperatingMode.DISCOVERY


# --- Facts (FR-P3, FR-P6) ---------------------------------------------------


def test_set_fact_validates_and_records_origin(session: Session, owner: User) -> None:
    fact = service.set_fact(
        session,
        owner.id,
        "major",
        "  Biology ",
        origin=FactOrigin.RESUME,
        origin_detail="resume.pdf",
    )
    session.commit()

    assert fact.value == "Biology"
    assert fact.origin is FactOrigin.RESUME
    assert fact.origin_detail == "resume.pdf"


def test_invalid_fact_is_not_saved(session: Session, owner: User) -> None:
    with pytest.raises(FactValidationError):
        service.set_fact(session, owner.id, "gpa", 7.0, origin=Q)

    assert not service.list_facts(session, owner.id)


def test_editing_a_fact_replaces_value_and_origin(
    session: Session, owner: User
) -> None:
    service.set_fact(session, owner.id, "gpa", 3.6, origin=FactOrigin.RESUME)
    service.set_fact(session, owner.id, "gpa", 3.7, origin=FactOrigin.MANUAL)
    session.commit()

    facts = service.list_facts(session, owner.id)
    assert len(facts) == 1
    assert facts[0].value == 3.7
    assert facts[0].origin is FactOrigin.MANUAL


def test_sensitive_fact_can_be_deleted(session: Session, owner: User) -> None:
    service.set_fact(session, owner.id, "citizenship_status", "us_citizen", origin=Q)
    service.delete_fact(session, owner.id, "citizenship_status")

    assert not service.list_facts(session, owner.id)


def test_deleting_a_missing_fact_raises(session: Session, owner: User) -> None:
    with pytest.raises(service.NotFoundError):
        service.delete_fact(session, owner.id, "gpa")


def test_custom_key_cannot_go_through_set_fact(session: Session, owner: User) -> None:
    with pytest.raises(FactValidationError):
        service.set_fact(session, owner.id, "custom.anything", "x", origin=Q)


# --- Never ask twice (FR-P4) ------------------------------------------------


def test_missing_fact_keys_skips_facts_on_file(session: Session, owner: User) -> None:
    service.set_fact(session, owner.id, "major", "History", origin=Q)

    missing = service.missing_fact_keys(
        session, owner.id, ["gpa", "major", "state_of_residence", "gpa"]
    )

    assert missing == ["gpa", "state_of_residence"]


def test_same_custom_question_reuses_the_stored_answer(
    session: Session, owner: User
) -> None:
    question = "What is your favorite subject?"
    service.set_custom_fact(
        session,
        owner.id,
        question,
        "Chemistry",
        origin=FactOrigin.SCHOLARSHIP_ANSWER,
        origin_detail="Test Scholarship A",
    )
    key = service.custom_fact_key("  what is your FAVORITE subject ")

    assert key == "custom.what_is_your_favorite_subject"
    assert service.missing_fact_keys(session, owner.id, [key]) == []


@pytest.mark.parametrize("label", ["", "   ", "?!", "x" * 201])
def test_custom_fact_rejects_bad_questions(
    session: Session, owner: User, label: str
) -> None:
    with pytest.raises(FactValidationError):
        service.set_custom_fact(session, owner.id, label, "answer", origin=Q)


# --- Story bank (FR-P5) -----------------------------------------------------


def test_story_body_is_stored_exactly_as_written(session: Session, owner: User) -> None:
    body = "  I started a tutoring club.\n\nIt grew to 30 students.  "

    story = service.create_story(
        session,
        owner.id,
        title=" Tutoring club ",
        body=body,
        themes=["Leadership", " community   service ", "leadership", ""],
    )
    session.commit()

    assert story.body == body  # never rewritten
    assert story.title == "Tutoring club"
    assert story.themes == ["leadership", "community service"]


@pytest.mark.parametrize(
    ("title", "body", "themes"),
    [
        ("", "body", []),
        ("title", "   \n ", []),
        ("title", "body", [f"theme {i}" for i in range(11)]),
        ("title", "body", ["x" * 41]),
    ],
)
def test_invalid_story_is_rejected(
    session: Session, owner: User, title: str, body: str, themes: list[str]
) -> None:
    with pytest.raises(service.StoryValidationError):
        service.create_story(session, owner.id, title=title, body=body, themes=themes)


def test_stories_can_be_filtered_by_theme(session: Session, owner: User) -> None:
    service.create_story(session, owner.id, title="A", body="a", themes=["family"])
    service.create_story(session, owner.id, title="B", body="b", themes=["teamwork"])

    titles = [s.title for s in service.list_stories(session, owner.id, theme="Family")]

    assert titles == ["A"]


def test_update_and_delete_story(session: Session, owner: User) -> None:
    story = service.create_story(session, owner.id, title="Old", body="x", themes=[])

    service.update_story(
        session, owner.id, story.id, title="New", body="y", themes=["family"]
    )
    assert service.list_stories(session, owner.id)[0].title == "New"

    service.delete_story(session, owner.id, story.id)
    assert not service.list_stories(session, owner.id)


# --- User isolation and deletion (NFR-8, NFR-12) ----------------------------


def test_users_never_see_each_others_data(session: Session, owner: User) -> None:
    other = other_user(session)
    service.set_fact(session, other.id, "major", "Art", origin=Q)
    story = service.create_story(session, other.id, title="T", body="b", themes=[])

    assert not service.list_facts(session, owner.id)
    assert not service.list_stories(session, owner.id)
    with pytest.raises(service.NotFoundError):
        service.delete_story(session, owner.id, story.id)


def test_deleting_a_user_deletes_all_their_data(session: Session, owner: User) -> None:
    service.get_or_create_profile(session, owner.id)
    service.set_fact(session, owner.id, "major", "Physics", origin=Q)
    service.create_story(session, owner.id, title="T", body="b", themes=[])
    session.commit()

    session.delete(owner)
    session.commit()

    for model in (Profile, ProfileFact, Story):
        assert session.scalar(select(func.count()).select_from(model)) == 0

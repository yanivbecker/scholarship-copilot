"""Onboarding wizard rules (FR-P1, FR-P4, FR-P6). Fictional test data."""

import pytest
from sqlalchemy.orm import Session

from app.modules.profile import onboarding, service
from app.modules.profile.models import FactOrigin
from app.modules.users.models import User

FIRST, SECOND, *_, LAST = onboarding.STEP_KEYS


def progress(session: Session, user: User) -> onboarding.Progress:
    return onboarding.get_progress(service.get_or_create_profile(session, user.id))


def finish_all(session: Session, user: User) -> None:
    for key in onboarding.STEP_KEYS:
        onboarding.submit_step(session, user.id, key, {})


def test_new_student_starts_at_the_first_step(session: Session, owner: User) -> None:
    p = progress(session, owner)

    assert not p.completed
    assert p.next_step == FIRST
    assert p.completed_at is None


def test_progress_is_resumable(session: Session, owner: User) -> None:
    onboarding.submit_step(session, owner.id, FIRST, {})
    session.commit()
    session.expire_all()  # as if the browser closed and the page reloaded

    p = progress(session, owner)
    assert p.completed == (FIRST,)
    assert p.next_step == SECOND


def test_answers_are_saved_with_questionnaire_origin(
    session: Session, owner: User
) -> None:
    onboarding.submit_step(
        session, owner.id, "basics", {"major": "Test Major", "full_name": "Test Name"}
    )

    facts = {f.key: f for f in service.list_facts(session, owner.id)}
    assert facts["major"].value == "Test Major"
    assert facts["major"].origin is FactOrigin.QUESTIONNAIRE


def test_one_bad_answer_saves_nothing_and_reports_every_problem(
    session: Session, owner: User
) -> None:
    onboarding.submit_step(session, owner.id, "basics", {})
    onboarding.submit_step(session, owner.id, "resume", {})

    with pytest.raises(onboarding.OnboardingError) as caught:
        onboarding.submit_step(
            session,
            owner.id,
            "questionnaire",
            {"gpa": 9.0, "state_of_residence": "Ohio", "pell_eligible": "yes"},
        )

    assert set(caught.value.field_errors) == {"gpa", "pell_eligible"}
    assert not service.list_facts(session, owner.id)  # Ohio wasn't saved either
    assert progress(session, owner).next_step == "questionnaire"


def test_facts_from_another_step_are_rejected(session: Session, owner: User) -> None:
    with pytest.raises(onboarding.OnboardingError) as caught:
        onboarding.submit_step(session, owner.id, "basics", {"gpa": 3.5})

    assert "gpa" in caught.value.field_errors


def test_sensitive_facts_are_optional(session: Session, owner: User) -> None:
    for key in ("basics", "resume"):
        onboarding.submit_step(session, owner.id, key, {})

    result = onboarding.submit_step(session, owner.id, "questionnaire", {"gpa": 3.2})

    assert "questionnaire" in result.completed


def test_cannot_skip_ahead(session: Session, owner: User) -> None:
    with pytest.raises(onboarding.OnboardingError, match="earlier steps"):
        onboarding.submit_step(session, owner.id, LAST, {})


def test_resubmitting_an_earlier_step_keeps_progress(
    session: Session, owner: User
) -> None:
    for key in ("basics", "resume", "questionnaire"):
        onboarding.submit_step(session, owner.id, key, {})

    result = onboarding.submit_step(session, owner.id, "basics", {"major": "Art"})

    assert result.next_step == "preferences"


def test_finishing_the_last_step_completes_onboarding(
    session: Session, owner: User
) -> None:
    finish_all(session, owner)

    p = progress(session, owner)
    assert p.next_step is None
    assert p.completed == onboarding.STEP_KEYS
    assert p.completed_at is not None


def test_unknown_step(session: Session, owner: User) -> None:
    with pytest.raises(onboarding.OnboardingError, match="Unknown"):
        onboarding.submit_step(session, owner.id, "nope", {})

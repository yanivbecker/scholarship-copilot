"""The onboarding wizard (FR-P1): ordered steps, resumable at any point.

Progress lives on the profile (`onboarding_step` = last finished step), so
closing the browser mid-way and coming back continues where you left off.
Fact steps only need the facts that aren't on file yet (FR-P4); the frontend
asks GET /facts/missing with each step's keys.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.profile import service
from app.modules.profile.catalog import CATALOG, FieldErrorsError, validate_facts
from app.modules.profile.models import FactOrigin, Profile


@dataclass(frozen=True)
class Step:
    """One wizard step. `fact_keys` is empty for steps that aren't fact forms."""

    key: str
    label: str
    fact_keys: tuple[str, ...] = ()


STEPS: tuple[Step, ...] = (
    Step(
        "basics",
        "Basics and school",
        (
            "full_name",
            "school_name",
            "education_level",
            "enrollment_status",
            "major",
            "expected_graduation_year",
        ),
    ),
    Step("resume", "Resume (optional)"),
    Step(
        "questionnaire",
        "A few more questions",
        (
            "gpa",
            "gpa_scale",
            "country_of_residence",
            "state_of_residence",
            "intended_career",
            "community_service_hours",
            # Sensitive, always optional (FR-P6):
            "citizenship_status",
            "first_generation",
            "pell_eligible",
        ),
    ),
    Step("preferences", "Mode and notifications"),
    Step("sources", "First sources"),
)

STEP_KEYS = tuple(step.key for step in STEPS)
_BY_KEY = {step.key: step for step in STEPS}
if any(k not in CATALOG for s in STEPS for k in s.fact_keys):  # pragma: no cover
    raise RuntimeError("An onboarding step uses a fact key missing from CATALOG")


class OnboardingError(FieldErrorsError):
    """Bad step or bad answers. `field_errors` maps fact keys to messages."""


@dataclass(frozen=True)
class Progress:
    """Where the student is in the wizard."""

    completed: tuple[str, ...]
    next_step: str | None  # None once every step is done
    completed_at: datetime | None


def get_progress(profile: Profile) -> Progress:
    done = profile.onboarding_step
    count = STEP_KEYS.index(done) + 1 if done in STEP_KEYS else 0
    return Progress(
        completed=STEP_KEYS[:count],
        next_step=STEP_KEYS[count] if count < len(STEP_KEYS) else None,
        completed_at=profile.onboarding_completed_at,
    )


def submit_step(
    session: Session, user_id: int, step_key: str, facts: dict[str, object]
) -> Progress:
    """Save a step's answers (all or nothing) and mark the step finished.

    Every answer is validated before anything is saved, and *all* problems are
    reported at once, so the student can fix them in one go. Empty answers are
    simply left out by the frontend: every fact is optional.
    """
    step = _BY_KEY.get(step_key)
    if step is None:
        raise OnboardingError(f"Unknown onboarding step: {step_key!r}")

    profile = service.get_or_create_profile(session, user_id)
    progress = get_progress(profile)
    if progress.next_step is not None and STEP_KEYS.index(step_key) > STEP_KEYS.index(
        progress.next_step
    ):
        raise OnboardingError("Finish the earlier steps first.")

    clean, errors = validate_facts(
        facts,
        is_allowed=lambda key: key in step.fact_keys,
        not_allowed_message=lambda key: f"{key!r} isn't part of the {step.label} step.",
    )
    if errors:
        raise OnboardingError("Some answers need fixing.", errors)

    for key, value in clean.items():
        service.set_fact(session, user_id, key, value, origin=FactOrigin.QUESTIONNAIRE)

    # Going back and re-submitting an earlier step never moves progress back.
    if step_key not in progress.completed:
        profile.onboarding_step = step_key
    if step_key == STEP_KEYS[-1] and profile.onboarding_completed_at is None:
        profile.onboarding_completed_at = datetime.now(UTC)
    session.flush()
    return get_progress(profile)

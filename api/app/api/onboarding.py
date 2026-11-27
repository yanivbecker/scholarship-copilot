"""The onboarding wizard (FR-P1)."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.modules.profile import onboarding, service
from app.modules.profile.schemas import (
    OnboardingOut,
    OnboardingStepIn,
    OnboardingStepOut,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _out(progress: onboarding.Progress) -> OnboardingOut:
    return OnboardingOut(
        steps=[
            OnboardingStepOut(key=s.key, label=s.label, fact_keys=list(s.fact_keys))
            for s in onboarding.STEPS
        ],
        completed=list(progress.completed),
        next_step=progress.next_step,
        completed_at=progress.completed_at,
    )


@router.get("")
def get_onboarding(session: SessionDep, user: CurrentUser) -> OnboardingOut:
    profile = service.get_or_create_profile(session, user.id)
    session.commit()
    return _out(onboarding.get_progress(profile))


@router.post("/steps/{step}")
def submit_onboarding_step(
    step: str, body: OnboardingStepIn, session: SessionDep, user: CurrentUser
) -> OnboardingOut:
    progress = onboarding.submit_step(session, user.id, step, dict(body.facts))
    session.commit()
    return _out(progress)

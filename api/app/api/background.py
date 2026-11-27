"""Background running on/off from the Settings page (FR-N2).

The same code as `scholar background on|off|status`. Switching on installs
and loads the launchd agent for this Mac user (the owner's action).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.modules.background import service as background
from app.modules.background.launchd import Agent
from app.modules.jobs.schemas import JobRunOut

router = APIRouter(prefix="/background", tags=["background"])
AgentDep = Annotated[Agent, Depends(background.get_agent)]


class BackgroundOut(BaseModel):
    """Whether background running is on, and what launchd says."""

    enabled: bool
    installed: bool
    loaded: bool
    dry_run: bool
    schedule: str
    summary: str
    last_scheduled_run: JobRunOut | None


class BackgroundIn(BaseModel):
    """Switch background running on (install + load) or off (unload + remove)."""

    enabled: bool


def _out(session: SessionDep, user_id: int, agent: Agent) -> BackgroundOut:
    state = background.status(session, user_id, agent)
    session.commit()
    last = state.last_scheduled_run
    return BackgroundOut(
        enabled=state.enabled,
        installed=state.installed,
        loaded=state.loaded,
        dry_run=state.dry_run,
        schedule=state.schedule,
        summary=state.summary,
        last_scheduled_run=JobRunOut.model_validate(last) if last else None,
    )


@router.get("")
def get_background(
    session: SessionDep, user: CurrentUser, agent: AgentDep
) -> BackgroundOut:
    return _out(session, user.id, agent)


@router.put("")
def set_background(
    body: BackgroundIn, session: SessionDep, user: CurrentUser, agent: AgentDep
) -> BackgroundOut:
    background.switch(session, user.id, agent, on=body.enabled)
    return _out(session, user.id, agent)

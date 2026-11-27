"""The story bank (FR-P5)."""

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.modules.profile import service
from app.modules.profile.schemas import StoryIn, StoryOut, ThemesOut

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("")
def list_stories(
    session: SessionDep, user: CurrentUser, theme: str | None = None
) -> list[StoryOut]:
    stories = service.list_stories(session, user.id, theme=theme)
    return [StoryOut.model_validate(s) for s in stories]


@router.get("/themes")
def get_story_themes() -> ThemesOut:
    return ThemesOut(suggested=list(service.SUGGESTED_THEMES))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_story(body: StoryIn, session: SessionDep, user: CurrentUser) -> StoryOut:
    story = service.create_story(
        session, user.id, title=body.title, body=body.body, themes=body.themes
    )
    session.commit()
    return StoryOut.model_validate(story)


@router.put("/{story_id}")
def update_story(
    story_id: int, body: StoryIn, session: SessionDep, user: CurrentUser
) -> StoryOut:
    story = service.update_story(
        session,
        user.id,
        story_id,
        title=body.title,
        body=body.body,
        themes=body.themes,
    )
    session.commit()
    return StoryOut.model_validate(story)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(story_id: int, session: SessionDep, user: CurrentUser) -> Response:
    service.delete_story(session, user.id, story_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

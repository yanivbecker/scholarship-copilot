"""Database queries for the profile module. No business rules here.

Every query is scoped by user_id, so one user's data is never returned for
another (NFR-8).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.profile.models import Profile, ProfileFact, Story


def get_profile(session: Session, user_id: int) -> Profile | None:
    return session.scalars(select(Profile).where(Profile.user_id == user_id)).first()


def get_fact(session: Session, user_id: int, key: str) -> ProfileFact | None:
    return session.scalars(
        select(ProfileFact).where(
            ProfileFact.user_id == user_id, ProfileFact.key == key
        )
    ).first()


def list_facts(session: Session, user_id: int) -> list[ProfileFact]:
    return list(
        session.scalars(
            select(ProfileFact)
            .where(ProfileFact.user_id == user_id)
            .order_by(ProfileFact.key)
        )
    )


def fact_keys(session: Session, user_id: int) -> set[str]:
    return set(
        session.scalars(select(ProfileFact.key).where(ProfileFact.user_id == user_id))
    )


def get_story(session: Session, user_id: int, story_id: int) -> Story | None:
    return session.scalars(
        select(Story).where(Story.user_id == user_id, Story.id == story_id)
    ).first()


def list_stories(session: Session, user_id: int) -> list[Story]:
    return list(
        session.scalars(
            select(Story).where(Story.user_id == user_id).order_by(Story.id.desc())
        )
    )

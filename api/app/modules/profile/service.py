"""Profile business rules: validated facts, "never ask twice", story bank.

Services change the session but don't commit. The caller (an API request or
a job) commits once at the end, so a multi-step change is all-or-nothing.
"""

import re
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.modules.profile import repository
from app.modules.profile.catalog import (
    MAX_TEXT_LENGTH,
    FactValidationError,
    get_definition,
    validate_value,
)
from app.modules.profile.models import (
    FactOrigin,
    OperatingMode,
    Profile,
    ProfileFact,
    Story,
)

CUSTOM_PREFIX = "custom."
MAX_LABEL_LENGTH = 200

MAX_TITLE_LENGTH = 200
MAX_STORY_LENGTH = 20_000
MAX_THEMES = 10
MAX_THEME_LENGTH = 40

# Shown as suggestions in the UI; students can add their own themes too.
SUGGESTED_THEMES = (
    "academic achievement",
    "adversity",
    "career goals",
    "community service",
    "creativity",
    "diversity and identity",
    "family",
    "leadership",
    "teamwork",
    "work experience",
)


class NotFoundError(LookupError):
    """The requested record doesn't exist for this user."""


class StoryValidationError(ValueError):
    """A story doesn't meet the rules. The message is user-facing."""


# --- Profile ---------------------------------------------------------------


def get_or_create_profile(session: Session, user_id: int) -> Profile:
    profile = repository.get_profile(session, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, operating_mode=OperatingMode.HYBRID)
        session.add(profile)
        session.flush()
    return profile


def set_operating_mode(session: Session, user_id: int, mode: OperatingMode) -> Profile:
    """FR-P7: the mode can be changed at any time."""
    profile = get_or_create_profile(session, user_id)
    profile.operating_mode = mode
    session.flush()
    return profile


# --- Facts -----------------------------------------------------------------


def set_fact(  # pylint: disable=too-many-arguments
    session: Session,
    user_id: int,
    key: str,
    value: object,
    *,
    origin: FactOrigin,
    origin_detail: str | None = None,
) -> ProfileFact:
    """Create or replace a catalog fact after validating it (FR-P3).

    The origin always describes the *current* value: editing a resume-imported
    GPA by hand makes its origin MANUAL.
    """
    if key.startswith(CUSTOM_PREFIX):
        raise FactValidationError("Use set_custom_fact for custom facts.")
    clean_value = validate_value(get_definition(key), value)
    return _upsert_fact(
        session,
        user_id,
        key,
        label=None,
        value=clean_value,
        origin=origin,
        origin_detail=origin_detail,
    )


def set_custom_fact(  # pylint: disable=too-many-arguments
    session: Session,
    user_id: int,
    label: str,
    value: str,
    *,
    origin: FactOrigin,
    origin_detail: str | None = None,
) -> ProfileFact:
    """Store an answer to a question that isn't in the catalog (FR-P4).

    The key comes from the question text, so the same question asked by a
    second scholarship finds the stored answer instead of asking again.
    """
    clean_label = label.strip()
    if not clean_label or len(clean_label) > MAX_LABEL_LENGTH:
        raise FactValidationError(
            f"The question must be 1-{MAX_LABEL_LENGTH} characters."
        )
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > MAX_TEXT_LENGTH:
        raise FactValidationError(
            f"The answer must be 1-{MAX_TEXT_LENGTH} characters of text."
        )
    return _upsert_fact(
        session,
        user_id,
        custom_fact_key(clean_label),
        label=clean_label,
        value=text,
        origin=origin,
        origin_detail=origin_detail,
    )


def custom_fact_key(label: str) -> str:
    """ "What is your favorite subject?" -> "custom.what_is_your_favorite_subject"."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:80]
    if not slug:
        raise FactValidationError("The question must contain letters or numbers.")
    return CUSTOM_PREFIX + slug


def _upsert_fact(  # pylint: disable=too-many-arguments
    session: Session,
    user_id: int,
    key: str,
    *,
    label: str | None,
    value: object,
    origin: FactOrigin,
    origin_detail: str | None,
) -> ProfileFact:
    fact = repository.get_fact(session, user_id, key)
    if fact is None:
        fact = ProfileFact(user_id=user_id, key=key)
        session.add(fact)
    fact.label = label
    fact.value = value  # type: ignore[assignment]  # validated by the caller
    fact.origin = origin
    fact.origin_detail = origin_detail
    session.flush()
    return fact


def list_facts(session: Session, user_id: int) -> list[ProfileFact]:
    return repository.list_facts(session, user_id)


def delete_fact(session: Session, user_id: int, key: str) -> None:
    """FR-P6: every fact can be removed, including sensitive ones."""
    fact = repository.get_fact(session, user_id, key)
    if fact is None:
        raise NotFoundError(f"No fact {key!r}")
    session.delete(fact)
    session.flush()


def missing_fact_keys(session: Session, user_id: int, keys: Iterable[str]) -> list[str]:
    """FR-P4: of the facts we'd like to ask about, which are not on file yet?

    Forms and the wizard call this so they only ask for what's missing.
    Keeps the caller's order and drops duplicates.
    """
    on_file = repository.fact_keys(session, user_id)
    return [key for key in dict.fromkeys(keys) if key not in on_file]


# --- Story bank ------------------------------------------------------------


def create_story(
    session: Session, user_id: int, *, title: str, body: str, themes: Iterable[str]
) -> Story:
    story = Story(user_id=user_id)
    _apply_story_fields(story, title=title, body=body, themes=themes)
    session.add(story)
    session.flush()
    return story


def update_story(  # pylint: disable=too-many-arguments
    session: Session,
    user_id: int,
    story_id: int,
    *,
    title: str,
    body: str,
    themes: Iterable[str],
) -> Story:
    story = repository.get_story(session, user_id, story_id)
    if story is None:
        raise NotFoundError(f"No story {story_id}")
    _apply_story_fields(story, title=title, body=body, themes=themes)
    session.flush()
    return story


def delete_story(session: Session, user_id: int, story_id: int) -> None:
    story = repository.get_story(session, user_id, story_id)
    if story is None:
        raise NotFoundError(f"No story {story_id}")
    session.delete(story)
    session.flush()


def list_stories(
    session: Session, user_id: int, *, theme: str | None = None
) -> list[Story]:
    stories = repository.list_stories(session, user_id)
    if theme is None:
        return stories
    wanted = normalize_theme(theme)
    return [s for s in stories if wanted in s.themes]


def normalize_theme(theme: str) -> str:
    """ "  Community   Service " -> "community service"."""
    return " ".join(theme.split()).lower()


def _apply_story_fields(
    story: Story, *, title: str, body: str, themes: Iterable[str]
) -> None:
    clean_title = title.strip()
    if not clean_title or len(clean_title) > MAX_TITLE_LENGTH:
        raise StoryValidationError(f"Title must be 1-{MAX_TITLE_LENGTH} characters.")
    # The body is the student's own words: validate it, but never alter it.
    if not body.strip():
        raise StoryValidationError("The story can't be empty.")
    if len(body) > MAX_STORY_LENGTH:
        raise StoryValidationError(
            f"The story must be at most {MAX_STORY_LENGTH} characters."
        )
    clean_themes = list(dict.fromkeys(normalize_theme(t) for t in themes))
    clean_themes = [t for t in clean_themes if t]
    if len(clean_themes) > MAX_THEMES:
        raise StoryValidationError(f"Use at most {MAX_THEMES} themes.")
    if any(len(t) > MAX_THEME_LENGTH for t in clean_themes):
        raise StoryValidationError(
            f"Each theme must be at most {MAX_THEME_LENGTH} characters."
        )
    story.title = clean_title
    story.body = body
    story.themes = clean_themes

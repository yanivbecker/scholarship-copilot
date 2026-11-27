"""Request and response bodies for the profile API.

Request values use Pydantic's Strict* types so nothing gets converted on the
way in ("3.8" stays a string and is then rejected by the catalog). Responses
are what the generated TypeScript types are built from.
"""

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)

from app.modules.profile.catalog import FactSection, FactType
from app.modules.profile.models import FactOrigin, OperatingMode

type FactValueIn = StrictStr | StrictInt | StrictFloat | StrictBool | list[StrictStr]
type FactValueOut = str | int | float | bool | list[str]


class _FromORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Profile ---


class ProfileOut(BaseModel):
    """The student's settings and onboarding progress."""

    display_name: str
    operating_mode: OperatingMode
    onboarding_step: str | None
    onboarding_completed_at: datetime | None


class ProfileUpdate(BaseModel):
    """Fields to change. Omitted fields stay as they are."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    operating_mode: OperatingMode | None = None


# --- Catalog ---


class ChoiceOut(BaseModel):
    """One option of a choice fact: the stored value and its display label."""

    value: str
    label: str


class FactDefinitionOut(BaseModel):
    """One fact the app knows about, with the rules its value must follow."""

    key: str
    label: str
    type: FactType
    section: FactSection
    sensitive: bool
    help: str
    choices: list[ChoiceOut]
    min_value: float | None
    max_value: float | None


class SectionOut(BaseModel):
    """A group of facts, in display order."""

    key: FactSection
    label: str
    sensitive: bool
    facts: list[FactDefinitionOut]


class CatalogOut(BaseModel):
    """The whole fact catalog, grouped by section."""

    sections: list[SectionOut]


# --- Facts ---


class FactOut(_FromORM):
    """A stored fact. `label` is set for custom (scholarship-specific) facts."""

    key: str
    label: str | None
    value: FactValueOut
    origin: FactOrigin
    origin_detail: str | None
    updated_at: datetime


class FactIn(BaseModel):
    """A new value for a catalog fact.

    Only the origins a person can produce in the app's forms are accepted here.
    Resume and scholarship-answer origins are set by their own flows.
    """

    value: FactValueIn
    origin: Literal[FactOrigin.QUESTIONNAIRE, FactOrigin.MANUAL] = FactOrigin.MANUAL


class MissingFactsOut(BaseModel):
    """Which of the requested fact keys are not on file yet (FR-P4)."""

    missing: list[str]


# --- Stories ---


class StoryIn(BaseModel):
    """A story to create or replace. Detailed rules are checked by the service."""

    title: str
    body: str
    themes: list[str] = []


class StoryOut(_FromORM):
    """A story from the story bank, exactly as written."""

    id: int
    title: str
    body: str
    themes: list[str]
    created_at: datetime
    updated_at: datetime


class ThemesOut(BaseModel):
    """Suggested themes for tagging stories."""

    suggested: list[str]

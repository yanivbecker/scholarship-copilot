"""The fact catalog: every profile fact the app knows how to store and compare.

Each fact has a stable key, a type, and validation rules. Values are always
validated against this catalog before they are saved (FR-P3), so the
eligibility engine (Phase 5) can compare them with plain, deterministic code.

Sensitive facts (citizenship, financial, demographic) are always optional
(FR-P6): nothing in the app may require them.

Adding a fact: append a FactDefinition below. Keys are permanent once real
data uses them; rename by migrating data, never by editing the key in place.
"""

import datetime as dt
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

# What a validated value looks like once stored (JSON-compatible).
type FactValue = str | int | float | bool | list[str]

MAX_TEXT_LENGTH = 500


class FactType(StrEnum):
    """How a fact's value is shaped and validated."""

    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"  # stored as an ISO string, "YYYY-MM-DD"
    CHOICE = "choice"  # exactly one of `choices`
    MULTI_CHOICE = "multi_choice"  # zero or more of `choices`


class FactSection(StrEnum):
    """Groups facts for display (profile editor, onboarding steps)."""

    BASICS = "basics"
    EDUCATION = "education"
    LOCATION = "location"
    CITIZENSHIP = "citizenship"
    FINANCIAL = "financial"
    DEMOGRAPHIC = "demographic"
    ACTIVITIES = "activities"


# Display order and labels for the profile editor and the wizard.
SECTION_LABELS: dict[FactSection, str] = {
    FactSection.BASICS: "Basics",
    FactSection.EDUCATION: "Education",
    FactSection.LOCATION: "Location",
    FactSection.CITIZENSHIP: "Citizenship",
    FactSection.FINANCIAL: "Financial",
    FactSection.DEMOGRAPHIC: "Demographic",
    FactSection.ACTIVITIES: "Activities",
}

SENSITIVE_SECTIONS = frozenset(
    {FactSection.CITIZENSHIP, FactSection.FINANCIAL, FactSection.DEMOGRAPHIC}
)


@dataclass(frozen=True, kw_only=True)
class FactDefinition:  # pylint: disable=too-many-instance-attributes
    """One entry in the catalog."""

    key: str
    label: str
    type: FactType
    section: FactSection
    help: str = ""
    choices: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None

    @property
    def sensitive(self) -> bool:
        return self.section in SENSITIVE_SECTIONS


# Labels for choice values that "first_word rest" capitalization gets wrong.
_CHOICE_LABEL_OVERRIDES = {
    "us_citizen": "U.S. citizen",
    "daca": "DACA",
    "middle_eastern_or_north_african": "Middle Eastern or North African",
    "native_hawaiian_or_pacific_islander": "Native Hawaiian or Pacific Islander",
    "american_indian_or_alaska_native": "American Indian or Alaska Native",
    "black_or_african_american": "Black or African American",
    "hispanic_or_latino": "Hispanic or Latino",
}


def choice_label(value: str) -> str:
    """ "full_time" -> "Full time" (with overrides for names and acronyms)."""
    return _CHOICE_LABEL_OVERRIDES.get(value, value.replace("_", " ").capitalize())


class FactValidationError(ValueError):
    """A value doesn't fit its fact definition. The message is user-facing."""


S = FactSection
T = FactType

_DEFINITIONS: Sequence[FactDefinition] = (
    # --- Basics ---
    FactDefinition(key="full_name", label="Full name", type=T.TEXT, section=S.BASICS),
    FactDefinition(key="email", label="Email", type=T.TEXT, section=S.BASICS),
    FactDefinition(key="phone", label="Phone", type=T.TEXT, section=S.BASICS),
    FactDefinition(
        key="date_of_birth",
        label="Date of birth",
        type=T.DATE,
        section=S.BASICS,
        help="Some scholarships have age limits.",
    ),
    # --- Education ---
    FactDefinition(
        key="school_name",
        label="Current school",
        type=T.TEXT,
        section=S.EDUCATION,
    ),
    FactDefinition(
        key="education_level",
        label="Education level",
        type=T.CHOICE,
        section=S.EDUCATION,
        choices=("high_school", "undergraduate", "graduate", "other"),
    ),
    FactDefinition(
        key="enrollment_status",
        label="Enrollment status",
        type=T.CHOICE,
        section=S.EDUCATION,
        choices=("full_time", "part_time", "not_enrolled"),
    ),
    FactDefinition(
        key="expected_graduation_year",
        label="Expected graduation year",
        type=T.INTEGER,
        section=S.EDUCATION,
        min_value=1950,
        max_value=2100,
    ),
    FactDefinition(key="major", label="Major", type=T.TEXT, section=S.EDUCATION),
    FactDefinition(key="minor", label="Minor", type=T.TEXT, section=S.EDUCATION),
    FactDefinition(
        key="gpa",
        label="GPA",
        type=T.NUMBER,
        section=S.EDUCATION,
        min_value=0,
        max_value=5,
        help="As shown on your transcript.",
    ),
    FactDefinition(
        key="gpa_scale",
        label="GPA scale",
        type=T.NUMBER,
        section=S.EDUCATION,
        min_value=1,
        max_value=5,
        help="Usually 4.0. Needed to compare GPAs fairly.",
    ),
    FactDefinition(
        key="intended_career",
        label="Intended career or field",
        type=T.TEXT,
        section=S.EDUCATION,
    ),
    # --- Location ---
    FactDefinition(
        key="country_of_residence",
        label="Country of residence",
        type=T.TEXT,
        section=S.LOCATION,
    ),
    FactDefinition(
        key="state_of_residence",
        label="State of residence",
        type=T.TEXT,
        section=S.LOCATION,
        help="Many scholarships are limited to residents of one state.",
    ),
    FactDefinition(key="city", label="City", type=T.TEXT, section=S.LOCATION),
    # --- Citizenship (sensitive) ---
    FactDefinition(
        key="citizenship_status",
        label="Citizenship status",
        type=T.CHOICE,
        section=S.CITIZENSHIP,
        choices=(
            "us_citizen",
            "permanent_resident",
            "daca",
            "international_student",
            "other",
        ),
    ),
    # --- Financial (sensitive) ---
    FactDefinition(
        key="pell_eligible",
        label="Pell Grant eligible",
        type=T.BOOLEAN,
        section=S.FINANCIAL,
    ),
    FactDefinition(
        key="student_aid_index",
        label="Student Aid Index (SAI)",
        type=T.INTEGER,
        section=S.FINANCIAL,
        min_value=-1500,
        max_value=1_000_000,
        help="From your FAFSA Submission Summary.",
    ),
    FactDefinition(
        key="household_income",
        label="Household income (USD per year)",
        type=T.INTEGER,
        section=S.FINANCIAL,
        min_value=0,
        max_value=100_000_000,
    ),
    # --- Demographic (sensitive) ---
    FactDefinition(
        key="first_generation",
        label="First-generation college student",
        type=T.BOOLEAN,
        section=S.DEMOGRAPHIC,
        help="Neither parent completed a four-year degree.",
    ),
    FactDefinition(key="gender", label="Gender", type=T.TEXT, section=S.DEMOGRAPHIC),
    FactDefinition(
        key="race_ethnicity",
        label="Race / ethnicity",
        type=T.MULTI_CHOICE,
        section=S.DEMOGRAPHIC,
        choices=(
            "american_indian_or_alaska_native",
            "asian",
            "black_or_african_american",
            "hispanic_or_latino",
            "middle_eastern_or_north_african",
            "native_hawaiian_or_pacific_islander",
            "white",
            "other",
        ),
    ),
    FactDefinition(
        key="military_affiliation",
        label="Military affiliation",
        type=T.MULTI_CHOICE,
        section=S.DEMOGRAPHIC,
        choices=("veteran", "active_duty", "military_family"),
    ),
    FactDefinition(
        key="has_disability",
        label="Has a disability",
        type=T.BOOLEAN,
        section=S.DEMOGRAPHIC,
    ),
    # --- Activities ---
    FactDefinition(
        key="community_service_hours",
        label="Community service hours",
        type=T.INTEGER,
        section=S.ACTIVITIES,
        min_value=0,
        max_value=100_000,
    ),
)

CATALOG: dict[str, FactDefinition] = {d.key: d for d in _DEFINITIONS}
if len(CATALOG) != len(_DEFINITIONS):  # pragma: no cover - guards edits above
    raise RuntimeError("Duplicate key in the fact catalog")


class FieldErrorsError(ValueError):
    """Several facts failed at once. `field_errors` maps keys to messages."""

    def __init__(self, message: str, field_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.field_errors = field_errors or {}


def validate_facts(
    facts: Mapping[str, object],
    *,
    is_allowed: Callable[[str], bool],
    not_allowed_message: Callable[[str], str],
) -> tuple[dict[str, FactValue], dict[str, str]]:
    """Validate a batch of answers. Returns (clean values, errors by key).

    Collects *every* problem instead of stopping at the first, so a form can
    show all of them at once.
    """
    clean: dict[str, FactValue] = {}
    errors: dict[str, str] = {}
    for key, raw in facts.items():
        if not is_allowed(key):
            errors[key] = not_allowed_message(key)
            continue
        try:
            clean[key] = validate_value(get_definition(key), raw)
        except FactValidationError as exc:
            errors[key] = str(exc)
    return clean, errors


def get_definition(key: str) -> FactDefinition:
    try:
        return CATALOG[key]
    except KeyError:
        raise FactValidationError(f"Unknown fact: {key!r}") from None


# One return per fact type is the clearest shape for this dispatch.
def validate_value(  # pylint: disable=too-many-return-statements
    definition: FactDefinition, raw: object
) -> FactValue:
    """Check `raw` against `definition` and return the normalized value.

    Deliberately strict: no guessing ("yes" is not a boolean, "3.5" is not a
    number). The API and forms send properly typed JSON, so a mismatch means a
    bug or bad input, and silently converting it would hide that.
    """
    match definition.type:
        case FactType.TEXT:
            return _validate_text(definition, raw)
        case FactType.INTEGER:
            return _validate_integer(definition, raw)
        case FactType.NUMBER:
            return _validate_number(definition, raw)
        case FactType.BOOLEAN:
            if not isinstance(raw, bool):
                raise FactValidationError(f"{definition.label} must be true or false.")
            return raw
        case FactType.DATE:
            return _validate_date(definition, raw)
        case FactType.CHOICE:
            if raw not in definition.choices:
                options = ", ".join(definition.choices)
                raise FactValidationError(
                    f"{definition.label} must be one of: {options}."
                )
            return str(raw)
        case FactType.MULTI_CHOICE:
            return _validate_multi_choice(definition, raw)
        case _:  # a new FactType without a branch here fails type checking
            assert_never(definition.type)


def _validate_text(definition: FactDefinition, raw: object) -> str:
    if not isinstance(raw, str):
        raise FactValidationError(f"{definition.label} must be text.")
    text = raw.strip()
    if not text:
        raise FactValidationError(f"{definition.label} can't be empty.")
    if len(text) > MAX_TEXT_LENGTH:
        raise FactValidationError(
            f"{definition.label} must be at most {MAX_TEXT_LENGTH} characters."
        )
    return text


def _check_range(definition: FactDefinition, value: float) -> None:
    low, high = definition.min_value, definition.max_value
    if (low is not None and value < low) or (high is not None and value > high):
        raise FactValidationError(
            f"{definition.label} must be between {low:g} and {high:g}."
        )


def _validate_integer(definition: FactDefinition, raw: object) -> int:
    # bool is a subclass of int in Python, so reject it explicitly.
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise FactValidationError(f"{definition.label} must be a whole number.")
    _check_range(definition, raw)
    return raw


def _validate_number(definition: FactDefinition, raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise FactValidationError(f"{definition.label} must be a number.")
    if not math.isfinite(raw):
        raise FactValidationError(f"{definition.label} must be a finite number.")
    _check_range(definition, float(raw))
    return float(raw)


def _validate_date(definition: FactDefinition, raw: object) -> str:
    if not isinstance(raw, str):
        raise FactValidationError(f"{definition.label} must be a date (YYYY-MM-DD).")
    try:
        return dt.date.fromisoformat(raw).isoformat()
    except ValueError:
        raise FactValidationError(
            f"{definition.label} must be a date (YYYY-MM-DD)."
        ) from None


def _validate_multi_choice(definition: FactDefinition, raw: object) -> list[str]:
    if not isinstance(raw, list):
        raise FactValidationError(f"{definition.label} must be a list.")
    invalid = [item for item in raw if item not in definition.choices]
    if invalid:
        raise FactValidationError(
            f"{definition.label} has unknown options: {', '.join(map(str, invalid))}."
        )
    # Remove duplicates, keep the order the student chose.
    return list(dict.fromkeys(str(item) for item in raw))

"""Eligibility criterion kinds, and how their parameters are validated.

Each kind maps to catalog facts, so the eligibility engine (5.4) can compare
a criterion with the student's profile in plain code. Anything that doesn't
fit a kind exactly becomes FREE_TEXT, which stays "unknown" until the student
confirms it themselves (FR-E3). We never force a criterion into a kind it
doesn't really match: a wrong kind could produce a wrong verdict.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.modules.profile.catalog import CATALOG


class CriterionKind(StrEnum):
    """What a criterion checks. Parameters are documented per kind below."""

    GPA_MIN = "gpa_min"  # min (number), scale (number, optional)
    EDUCATION_LEVEL_IN = "education_level_in"  # values: education_level choices
    ENROLLMENT_STATUS_IN = "enrollment_status_in"  # values: enrollment choices
    GRAD_YEAR_BETWEEN = "grad_year_between"  # min / max year (one or both)
    STATE_IN = "state_in"  # values: US states (names or codes)
    COUNTRY_IN = "country_in"  # values: country names
    CITIZENSHIP_IN = "citizenship_in"  # values: citizenship_status choices
    MAJOR_IN = "major_in"  # values: fields of study, as written
    FIRST_GENERATION = "first_generation"  # no parameters
    PELL_ELIGIBLE = "pell_eligible"  # no parameters
    HAS_DISABILITY = "has_disability"  # no parameters
    MILITARY_AFFILIATION_IN = "military_affiliation_in"  # values: choices
    RACE_ETHNICITY_IN = "race_ethnicity_in"  # values: race_ethnicity choices
    HOUSEHOLD_INCOME_MAX = "household_income_max"  # max (USD per year)
    AGE_BETWEEN = "age_between"  # min / max age in years (one or both)
    COMMUNITY_SERVICE_MIN = "community_service_min"  # min hours
    FREE_TEXT = "free_text"  # anything else: the quote says it all


# Kinds whose values must be catalog choices, and which fact they refer to.
CHOICE_KINDS: dict[CriterionKind, str] = {
    CriterionKind.EDUCATION_LEVEL_IN: "education_level",
    CriterionKind.ENROLLMENT_STATUS_IN: "enrollment_status",
    CriterionKind.CITIZENSHIP_IN: "citizenship_status",
    CriterionKind.MILITARY_AFFILIATION_IN: "military_affiliation",
    CriterionKind.RACE_ETHNICITY_IN: "race_ethnicity",
}
FREE_VALUE_KINDS = frozenset(
    {CriterionKind.STATE_IN, CriterionKind.COUNTRY_IN, CriterionKind.MAJOR_IN}
)
FLAG_KINDS = frozenset(
    {
        CriterionKind.FIRST_GENERATION,
        CriterionKind.PELL_ELIGIBLE,
        CriterionKind.HAS_DISABILITY,
    }
)
# kind -> (allowed range of each bound, whether min, max are allowed)
RANGE_KINDS: dict[CriterionKind, tuple[float, float, bool, bool]] = {
    CriterionKind.GPA_MIN: (0, 5, True, False),
    CriterionKind.GRAD_YEAR_BETWEEN: (1950, 2100, True, True),
    CriterionKind.HOUSEHOLD_INCOME_MAX: (0, 100_000_000, False, True),
    CriterionKind.AGE_BETWEEN: (0, 120, True, True),
    CriterionKind.COMMUNITY_SERVICE_MIN: (0, 100_000, True, False),
}

MAX_VALUES = 60
MAX_VALUE_LENGTH = 100


class CriterionParamError(ValueError):
    """The parameters don't fit the kind (the criterion becomes free text)."""


@dataclass(frozen=True)
class RawCriterion:
    """A criterion as extracted (flat fields, before validation)."""

    kind: str
    quote: str
    min_number: float | None = None
    max_number: float | None = None
    scale: float | None = None
    values: tuple[str, ...] = ()


def clean_params(raw: RawCriterion) -> tuple[CriterionKind, dict[str, Any]]:
    """Validate the parameters for the kind. Raises CriterionParamError."""
    try:
        kind = CriterionKind(raw.kind)
    except ValueError:
        raise CriterionParamError(f"Unknown criterion kind {raw.kind!r}") from None

    if kind is CriterionKind.FREE_TEXT or kind in FLAG_KINDS:
        return kind, {}
    if kind in CHOICE_KINDS:
        return kind, {"values": _choice_values(kind, raw.values)}
    if kind in FREE_VALUE_KINDS:
        return kind, {"values": _free_values(raw.values)}
    return kind, _range_params(kind, raw)


def _choice_values(kind: CriterionKind, values: tuple[str, ...]) -> list[str]:
    allowed = CATALOG[CHOICE_KINDS[kind]].choices
    cleaned = list(dict.fromkeys(v.strip().lower() for v in values if v.strip()))
    if not cleaned:
        raise CriterionParamError(f"{kind} needs at least one value")
    unknown = [v for v in cleaned if v not in allowed]
    if unknown:
        raise CriterionParamError(f"{kind} has values outside the catalog: {unknown}")
    return cleaned


def _free_values(values: tuple[str, ...]) -> list[str]:
    cleaned = list(dict.fromkeys(" ".join(v.split()) for v in values if v.strip()))
    if not cleaned or len(cleaned) > MAX_VALUES:
        raise CriterionParamError(f"Needs 1-{MAX_VALUES} values")
    if any(len(v) > MAX_VALUE_LENGTH for v in cleaned):
        raise CriterionParamError("A value is too long")
    return cleaned


def _range_params(kind: CriterionKind, raw: RawCriterion) -> dict[str, Any]:
    low, high, min_allowed, max_allowed = RANGE_KINDS[kind]
    params: dict[str, Any] = {}
    for name, value, allowed in (
        ("min", raw.min_number, min_allowed),
        ("max", raw.max_number, max_allowed),
    ):
        if value is None:
            continue
        if not allowed:
            raise CriterionParamError(f"{kind} doesn't take a {name}")
        if not low <= value <= high:
            raise CriterionParamError(f"{kind} {name} {value} is out of range")
        params[name] = value
    if not params:
        raise CriterionParamError(f"{kind} needs a number")
    if "min" in params and "max" in params and params["min"] > params["max"]:
        raise CriterionParamError(f"{kind} min is above max")
    if kind is CriterionKind.GPA_MIN and raw.scale is not None:
        if not 1 <= raw.scale <= 5 or raw.scale < params["min"]:
            raise CriterionParamError("GPA scale is implausible")
        params["scale"] = raw.scale
    return params

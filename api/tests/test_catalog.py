"""Fact catalog validation (FR-P3, FR-P6). All values here are test-only."""

import math

import pytest

from app.modules.profile.catalog import (
    CATALOG,
    MAX_TEXT_LENGTH,
    FactSection,
    FactType,
    FactValidationError,
    get_definition,
    validate_value,
)


def check(key: str, raw: object) -> object:
    return validate_value(get_definition(key), raw)


# --- The catalog itself ------------------------------------------------------


def test_every_choice_fact_has_choices() -> None:
    for definition in CATALOG.values():
        has_choices = bool(definition.choices)
        is_choice_type = definition.type in {FactType.CHOICE, FactType.MULTI_CHOICE}
        assert has_choices == is_choice_type, definition.key


def test_keys_are_snake_case_and_never_look_custom() -> None:
    for key in CATALOG:
        assert key.isidentifier() and key == key.lower(), key
        assert "." not in key, key  # "custom.<slug>" is reserved


@pytest.mark.parametrize(
    "key", ["citizenship_status", "household_income", "race_ethnicity"]
)
def test_sensitive_facts_are_flagged(key: str) -> None:
    assert get_definition(key).sensitive


def test_education_facts_are_not_sensitive() -> None:
    assert not get_definition("gpa").sensitive
    assert get_definition("gpa").section is FactSection.EDUCATION


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(FactValidationError, match="Unknown fact"):
        get_definition("favorite_color")


# --- Valid values are normalized --------------------------------------------


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        ("major", "  Computer Science ", "Computer Science"),
        ("expected_graduation_year", 2028, 2028),
        ("gpa", 4, 4.0),  # an int is a fine number
        ("gpa", 3.85, 3.85),
        ("pell_eligible", False, False),
        ("date_of_birth", "2006-03-09", "2006-03-09"),
        ("education_level", "undergraduate", "undergraduate"),
        ("race_ethnicity", ["asian", "white", "asian"], ["asian", "white"]),
        ("race_ethnicity", [], []),
        ("student_aid_index", -1500, -1500),  # SAI can be negative
    ],
)
def test_valid_values(key: str, raw: object, expected: object) -> None:
    assert check(key, raw) == expected


# --- Invalid values are rejected, never guessed -----------------------------


@pytest.mark.parametrize(
    ("key", "raw"),
    [
        ("major", ""),
        ("major", "   "),
        ("major", 42),
        ("major", "x" * (MAX_TEXT_LENGTH + 1)),
        ("expected_graduation_year", 2028.5),
        ("expected_graduation_year", "2028"),  # strings are not coerced
        ("expected_graduation_year", True),  # bool is an int in Python
        ("expected_graduation_year", 1900),  # below min
        ("gpa", 5.1),  # above max
        ("gpa", -0.1),
        ("gpa", "3.8"),
        ("gpa", math.nan),
        ("gpa", math.inf),
        ("pell_eligible", "yes"),
        ("pell_eligible", 1),
        ("date_of_birth", "03/09/2006"),
        ("date_of_birth", "2006-02-30"),
        ("education_level", "Undergraduate"),  # choices are exact
        ("race_ethnicity", "asian"),  # must be a list
        ("race_ethnicity", ["martian"]),
    ],
)
def test_invalid_values(key: str, raw: object) -> None:
    with pytest.raises(FactValidationError):
        check(key, raw)


def test_error_messages_use_the_label() -> None:
    with pytest.raises(FactValidationError, match="^GPA must be between 0 and 5"):
        check("gpa", 9)

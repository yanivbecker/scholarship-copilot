"""Rule-based resume suggestions (FR-P2). All resume text is fictional."""

import pytest

from app.modules.resume.extract import suggest_facts
from tests.resume_files import SAMPLE_LINES


def facts(text: str) -> dict[str, object]:
    return {s.key: s.value for s in suggest_facts(text)}


def test_sample_resume() -> None:
    assert facts("\n".join(SAMPLE_LINES)) == {
        "full_name": "Jordan A. Rivera",
        "email": "jordan.rivera@example.com",
        "phone": "(555) 123-4567",
        "school_name": "Northfield State University",
        "major": "Environmental Engineering",
        "education_level": "undergraduate",
        "gpa": 3.72,
        "gpa_scale": 4.0,
        "expected_graduation_year": 2027,
    }


def test_every_suggestion_shows_the_line_it_came_from() -> None:
    text = "\n".join(SAMPLE_LINES)
    for suggestion in suggest_facts(text):
        assert suggestion.evidence in text.splitlines()


@pytest.mark.parametrize(
    ("line", "gpa", "scale"),
    [
        ("GPA: 3.85", 3.85, None),
        ("Cumulative GPA 3.9 / 4.0", 3.9, 4.0),
        ("gpa - 4.25 out of 5", 4.25, 5.0),
    ],
)
def test_gpa_formats(line: str, gpa: float, scale: float | None) -> None:
    found = facts(line)
    assert found["gpa"] == gpa
    assert found.get("gpa_scale") == scale


def test_implausible_values_are_dropped_not_guessed() -> None:
    # 7.2 isn't a valid GPA (catalog max is 5), so nothing is suggested.
    assert "gpa" not in facts("GPA: 7.2")


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("Master of Science in Data Analytics", "graduate"),
        ("Bachelor of Arts, History", "undergraduate"),
        ("Lincoln High School 2019 - 2023", "high_school"),
    ],
)
def test_education_level_needs_an_explicit_degree_word(text: str, level: str) -> None:
    assert facts(text)["education_level"] == level


def test_no_level_without_a_degree_word() -> None:
    assert "education_level" not in facts("Northfield State University")


@pytest.mark.parametrize(
    "first_line", ["Curriculum Vitae", "RESUME", "Northfield State University"]
)
def test_headings_and_schools_are_not_names(first_line: str) -> None:
    assert facts(f"{first_line}\nnot a name line 123").get("full_name") is None


def test_name_below_a_resume_heading() -> None:
    assert facts("Resume\nAlex Test Person")["full_name"] == "Alex Test Person"


def test_school_name_keeps_high_school_and_drops_dates() -> None:
    assert facts("Lincoln High School 2019 - 2023")["school_name"] == (
        "Lincoln High School"
    )


def test_plain_text_gives_no_suggestions() -> None:
    assert facts("i like hiking and cooking on weekends") == {}

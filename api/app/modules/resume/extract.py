"""Rule-based fact suggestions from resume text (FR-P2, Phase 4).

Deterministic and conservative: a rule only fires on a clear pattern, and
every suggestion carries the line it came from (`evidence`), so the student
can see why it was suggested. Nothing here is saved; the student confirms
each value first. AI extraction (Phase 5) will add suggestions to the same
confirm step, never replace it.
"""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from app.modules.profile.catalog import (
    FactValidationError,
    FactValue,
    get_definition,
    validate_value,
)

MAX_EVIDENCE = 200


@dataclass(frozen=True)
class Suggestion:
    """One fact found in the resume, with the line that supports it."""

    key: str
    value: FactValue
    evidence: str


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
GPA = re.compile(
    r"\bGPA\b[^0-9]{0,15}(\d\.\d{1,3})(?:\s*(?:/|out of)\s*(\d(?:\.\d{1,2})?))?",
    re.IGNORECASE,
)
GRAD_YEAR = re.compile(
    r"\b(?:expected|anticipated|graduat\w*|class of)\b[^0-9\n]{0,40}((?:19|20)\d{2})",
    re.IGNORECASE,
)
SCHOOL = re.compile(
    r"\b(?:university|college|institute of technology|community college|"
    r"high school|academy|polytechnic)\b",
    re.IGNORECASE,
)
MAJOR = re.compile(
    r"\b(?:major(?:ing)?(?:\s+in)?\s*[:\-]?|"
    r"(?:B\.?S\.?|B\.?A\.?|Bachelor of (?:Science|Arts))\s*(?:degree\s+)?(?:in|,|-)\s*)"
    r"\s*([A-Z][A-Za-z&/ ]{2,60})"
)
# Degree words that make the education level unambiguous.
LEVELS = (
    (re.compile(r"\b(?:Ph\.?D|Master'?s?|M\.S\.|M\.A\.|MBA)\b"), "graduate"),
    (
        re.compile(r"\b(?:Bachelor'?s?|B\.S\.|B\.A\.|undergraduate)\b", re.I),
        "undergraduate",
    ),
    (re.compile(r"\bhigh school\b", re.I), "high_school"),
)
NAME_LINE = re.compile(r"[A-Z][a-zA-Z'\-]+(?: [A-Z][a-zA-Z'\-.]+){1,3}")
MONTH = (
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
    r"|spring|summer|fall|winter)[a-z]*\.?"
)
# A trailing date range like "  Aug 2023 – May 2027" (only month words allowed
# before the year, so "High School 2019" keeps "School").
DATES_AT_END = re.compile(
    rf"[\s,|–—-]*(?:{MONTH}\s+)?(?:19|20)\d{{2}}.*$", re.IGNORECASE
)


def suggest_facts(text: str) -> list[Suggestion]:
    """All suggestions that pass the catalog's validation, one per fact."""
    # Rules match on tidied lines (single spaces), but the evidence shown to
    # the student is the line exactly as it appears in the resume.
    original_of: dict[str, str] = {}
    for raw_line in text.splitlines():
        tidy = " ".join(raw_line.split())
        if tidy:
            original_of.setdefault(tidy, raw_line.strip())
    lines = list(original_of)
    found: dict[str, Suggestion] = {}
    for rule in RULES:
        for key, raw, line in rule(lines):
            if key in found:
                continue  # first, most prominent match wins
            try:
                value = validate_value(get_definition(key), raw)
            except FactValidationError:
                continue  # e.g. a "GPA" of 7.2: not a value we can trust
            found[key] = Suggestion(key, value, original_of[line][:MAX_EVIDENCE])
    return list(found.values())


type Hit = tuple[str, object, str]  # (fact key, raw value, evidence line)


HEADINGS = frozenset({"resume", "résumé", "curriculum vitae", "cv"})


def _name(lines: list[str]) -> Iterator[Hit]:
    # Resumes almost always start with the person's name on its own line,
    # sometimes below a "Resume" heading.
    for line in lines[:2]:
        if line.lower() in HEADINGS:
            continue
        if NAME_LINE.fullmatch(line) and not SCHOOL.search(line):
            yield "full_name", line, line
        return


def _contact(lines: list[str]) -> Iterator[Hit]:
    for line in lines[:15]:  # contact details sit at the top
        if m := EMAIL.search(line):
            yield "email", m.group(0), line
        if m := PHONE.search(line):
            yield "phone", m.group(0), line


def _gpa(lines: list[str]) -> Iterator[Hit]:
    for line in lines:
        if m := GPA.search(line):
            yield "gpa", float(m.group(1)), line
            if m.group(2):
                yield "gpa_scale", float(m.group(2)), line


def _graduation(lines: list[str]) -> Iterator[Hit]:
    for line in lines:
        if m := GRAD_YEAR.search(line):
            yield "expected_graduation_year", int(m.group(1)), line


def _education(lines: list[str]) -> Iterator[Hit]:
    for line in lines:
        if SCHOOL.search(line) and not EMAIL.search(line):
            school = _school_name(line)
            if school:
                yield "school_name", school, line
            break
    for line in lines:
        if m := MAJOR.search(line):
            major = re.split(r"\s{2,}|,| - | – |\|", m.group(1))[0].strip()
            yield "major", DATES_AT_END.sub("", major).strip(), line
    for pattern, level in LEVELS:
        for line in lines:
            if pattern.search(line):
                yield "education_level", level, line
                return


def _school_name(line: str) -> str:
    """ "Northfield State University, Springfield, IL  Aug 2023" -> the school."""
    text = DATES_AT_END.sub("", line.split("|")[0])
    parts = [p.strip(" -–—") for p in text.split(",")]
    # Keep comma parts up to the one that names the school; drop the city etc.
    for i, part in enumerate(parts):
        if SCHOOL.search(part):
            return ", ".join(parts[: i + 1]).strip()
    return ""


RULES: tuple[Callable[[list[str]], Iterator[Hit]], ...] = (
    _name,
    _contact,
    _gpa,
    _graduation,
    _education,
)

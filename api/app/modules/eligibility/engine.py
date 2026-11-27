"""The deterministic eligibility engine (FR-E1, FR-E2, FR-E3).

Plain code compares each criterion with the student's typed facts. No AI is
involved here: the same profile and criteria always give the same verdict,
and every result says why.

The one rule above all others: when in doubt, the answer is UNKNOWN (with a
question to ask), never NOT_MET. A wrong "not met" would hide a scholarship
the student could have won; a question just costs them a moment.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from app.modules.eligibility.places import canonical_country, canonical_state
from app.modules.profile.catalog import CATALOG, FactValue, choice_label
from app.modules.scholarships.criteria import CriterionKind

type Facts = Mapping[str, FactValue]


class Outcome(StrEnum):
    """The result for one criterion."""

    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


class Verdict(StrEnum):
    """The result for a scholarship cycle (FR-E2)."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    NEEDS_INFO = "needs_info"


@dataclass(frozen=True)
class Question:
    """Something the student can answer to resolve an UNKNOWN.

    `fact_key` set: answer it in the profile (and it's reused everywhere,
    FR-P4). `fact_key` None: confirm this criterion directly (FR-E3).
    """

    text: str
    fact_key: str | None = None
    optional: bool = False  # sensitive facts are always optional (FR-P6)


@dataclass(frozen=True)
class CriterionInput:
    """What the engine needs to know about one criterion."""

    id: int
    kind: str
    params: Mapping[str, Any]
    quote: str
    # The student's own answer for free-text criteria (FR-E3), if any.
    confirmation: bool | None = None


@dataclass(frozen=True)
class CriterionResult:
    """The outcome for one criterion, and why."""

    criterion_id: int
    outcome: Outcome
    reason: str
    question: Question | None = None


@dataclass(frozen=True)
class EligibilityResult:
    """The verdict for one cycle, every criterion's result, and the questions."""

    verdict: Verdict
    results: tuple[CriterionResult, ...]
    questions: tuple[Question, ...] = field(default=())
    summary: str = ""


# --- Helpers ------------------------------------------------------------------


def _ask_for(fact_key: str) -> Question:
    definition = CATALOG[fact_key]
    if definition.type.value == "boolean":
        text = f"{definition.label}: yes or no?"
    else:
        text = f"What is your {definition.label.lower()}?"
    return Question(text=text, fact_key=fact_key, optional=definition.sensitive)


def _missing(criterion: CriterionInput, fact_key: str) -> CriterionResult:
    label = CATALOG[fact_key].label
    return CriterionResult(
        criterion.id,
        Outcome.UNKNOWN,
        f"Your profile doesn't have your {label.lower()} yet.",
        _ask_for(fact_key),
    )


def _result(criterion: CriterionInput, met: bool, reason: str) -> CriterionResult:
    return CriterionResult(
        criterion.id, Outcome.MET if met else Outcome.NOT_MET, reason
    )


def _unknown(criterion: CriterionInput, reason: str, question: str) -> CriterionResult:
    return CriterionResult(criterion.id, Outcome.UNKNOWN, reason, Question(question))


def _labels(values: list[str]) -> str:
    return ", ".join(choice_label(v) for v in values)


# --- One rule per kind ----------------------------------------------------


def _gpa(value: float) -> str:
    """3 -> "3.0", 3.75 -> "3.75": GPAs read best with a decimal."""
    return f"{value:.1f}" if round(value, 1) == value else f"{value:g}"


def _gpa_min(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
    gpa = facts.get("gpa")
    if not isinstance(gpa, int | float) or isinstance(gpa, bool):
        return _missing(c, "gpa")
    minimum = float(c.params["min"])
    required_scale = c.params.get("scale")
    student_scale = facts.get("gpa_scale")
    if isinstance(student_scale, int | float) and not isinstance(student_scale, bool):
        if required_scale is not None and float(student_scale) != float(required_scale):
            # Converting between scales is a guess, so don't decide.
            return _unknown(
                c,
                f"Your GPA is on a {student_scale:g} scale; this asks for "
                f"{minimum:g} on a {required_scale:g} scale.",
                f"Does your GPA count as {minimum:g} or higher on a "
                f"{required_scale:g} scale?",
            )
    elif gpa > 4.0 and (required_scale is None or float(required_scale) <= 4.0):
        # Above 4.0 is probably weighted or a 5-point scale: ask first.
        return _missing(c, "gpa_scale")
    return _result(
        c,
        float(gpa) >= minimum,
        f"Your GPA is {_gpa(gpa)}; the minimum is {_gpa(minimum)}.",
    )


def _choice_in(
    fact_key: str,
) -> Callable[[CriterionInput, Facts, date], CriterionResult]:
    def rule(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
        value = facts.get(fact_key)
        if not isinstance(value, str):
            return _missing(c, fact_key)
        allowed = list(c.params["values"])
        label = CATALOG[fact_key].label.lower()
        return _result(
            c,
            value in allowed,
            f"Your {label} is {choice_label(value)}; allowed: {_labels(allowed)}.",
        )

    return rule


def _any_of(fact_key: str) -> Callable[[CriterionInput, Facts, date], CriterionResult]:
    def rule(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
        value = facts.get(fact_key)
        if not isinstance(value, list):
            return _missing(c, fact_key)
        allowed = list(c.params["values"])
        overlap = [v for v in value if v in allowed]
        label = CATALOG[fact_key].label.lower()
        if overlap:
            return _result(c, True, f"Your {label} includes {_labels(overlap)}.")
        return _result(c, False, f"This is limited to {_labels(allowed)}.")

    return rule


def _flag(fact_key: str) -> Callable[[CriterionInput, Facts, date], CriterionResult]:
    def rule(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
        value = facts.get(fact_key)
        if not isinstance(value, bool):
            return _missing(c, fact_key)
        label = CATALOG[fact_key].label
        return _result(c, value, f"{label}: {'yes' if value else 'no'}.")

    return rule


def _number_between(
    fact_key: str, unit: str
) -> Callable[[CriterionInput, Facts, date], CriterionResult]:
    def rule(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
        value = facts.get(fact_key)
        if not isinstance(value, int | float) or isinstance(value, bool):
            return _missing(c, fact_key)
        low, high = c.params.get("min"), c.params.get("max")
        ok = (low is None or value >= low) and (high is None or value <= high)
        bounds = " to ".join(f"{b:,g}" for b in (low, high) if b is not None)
        kind = "at least" if high is None else "at most" if low is None else "from"
        return _result(
            c, ok, f"Yours: {value:,g}{unit}; required {kind} {bounds}{unit}."
        )

    return rule


def _age_between(c: CriterionInput, facts: Facts, as_of: date) -> CriterionResult:
    born = facts.get("date_of_birth")
    if not isinstance(born, str):
        return _missing(c, "date_of_birth")
    birthday = date.fromisoformat(born)
    # Age on the as-of date (the deadline, when known): that's when it counts.
    age = (
        as_of.year
        - birthday.year
        - ((as_of.month, as_of.day) < (birthday.month, birthday.day))
    )
    low, high = c.params.get("min"), c.params.get("max")
    ok = (low is None or age >= low) and (high is None or age <= high)
    return _result(c, ok, f"You will be {age} on {as_of.isoformat()}.")


def _state_in(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
    state = facts.get("state_of_residence")
    if not isinstance(state, str):
        return _missing(c, "state_of_residence")
    allowed = list(c.params["values"])
    mine = canonical_state(state)
    theirs = [canonical_state(v) for v in allowed]
    if mine is not None and mine in theirs:
        return _result(c, True, f"You live in {mine}.")
    if mine is not None and all(t is not None for t in theirs):
        return _result(
            c, False, f"You live in {mine}; this is for {', '.join(allowed)}."
        )
    # An unrecognized name on either side: don't guess.
    return _unknown(
        c,
        "The state names couldn't be matched with certainty.",
        f"Do you live in one of: {', '.join(allowed)}?",
    )


def _country_in(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
    country = facts.get("country_of_residence")
    if not isinstance(country, str):
        return _missing(c, "country_of_residence")
    allowed = list(c.params["values"])
    if canonical_country(country) in {canonical_country(v) for v in allowed}:
        return _result(c, True, f"You live in {country}.")
    # Country names have many spellings; only a match is certain.
    return _unknown(
        c,
        f"{country} didn't match {', '.join(allowed)} exactly.",
        f"Do you live in one of: {', '.join(allowed)}?",
    )


def _major_in(c: CriterionInput, facts: Facts, _as_of: date) -> CriterionResult:
    major = facts.get("major")
    if not isinstance(major, str):
        return _missing(c, "major")
    allowed = list(c.params["values"])
    mine = " ".join(major.lower().split())
    for value in allowed:
        theirs = " ".join(value.lower().split())
        if mine == theirs or mine in theirs or theirs in mine:
            return _result(c, True, f"Your major ({major}) matches {value}.")
    # Fields of study overlap in ways a word match can't judge.
    return _unknown(
        c,
        f"Your major ({major}) isn't one of the listed names.",
        f"Does your major count as one of: {', '.join(allowed)}?",
    )


def _free_text(c: CriterionInput, _facts: Facts, _as_of: date) -> CriterionResult:
    if c.confirmation is None:
        return _unknown(
            c,
            "This requirement needs your judgment.",
            f"Do you meet this requirement: '{c.quote}'",
        )
    return _result(
        c,
        c.confirmation,
        "You confirmed you meet this."
        if c.confirmation
        else "You said you don't meet this.",
    )


RULES: dict[CriterionKind, Callable[[CriterionInput, Facts, date], CriterionResult]] = {
    CriterionKind.GPA_MIN: _gpa_min,
    CriterionKind.EDUCATION_LEVEL_IN: _choice_in("education_level"),
    CriterionKind.ENROLLMENT_STATUS_IN: _choice_in("enrollment_status"),
    CriterionKind.CITIZENSHIP_IN: _choice_in("citizenship_status"),
    CriterionKind.MILITARY_AFFILIATION_IN: _any_of("military_affiliation"),
    CriterionKind.RACE_ETHNICITY_IN: _any_of("race_ethnicity"),
    CriterionKind.FIRST_GENERATION: _flag("first_generation"),
    CriterionKind.PELL_ELIGIBLE: _flag("pell_eligible"),
    CriterionKind.HAS_DISABILITY: _flag("has_disability"),
    CriterionKind.GRAD_YEAR_BETWEEN: _number_between("expected_graduation_year", ""),
    CriterionKind.HOUSEHOLD_INCOME_MAX: _number_between("household_income", " USD"),
    CriterionKind.COMMUNITY_SERVICE_MIN: _number_between(
        "community_service_hours", " hours"
    ),
    CriterionKind.AGE_BETWEEN: _age_between,
    CriterionKind.STATE_IN: _state_in,
    CriterionKind.COUNTRY_IN: _country_in,
    CriterionKind.MAJOR_IN: _major_in,
    CriterionKind.FREE_TEXT: _free_text,
}


# --- Putting it together --------------------------------------------------


def evaluate_criterion(c: CriterionInput, facts: Facts, as_of: date) -> CriterionResult:
    try:
        rule = RULES[CriterionKind(c.kind)]
        return rule(c, facts, as_of)
    except (KeyError, ValueError, TypeError):
        # Stored data we can't interpret (e.g. from an older version): ask.
        return _unknown(
            c,
            "This requirement couldn't be checked automatically.",
            f"Do you meet: '{c.quote}'",
        )


def evaluate(
    criteria: list[CriterionInput], facts: Facts, as_of: date
) -> EligibilityResult:
    """FR-E2: any not met -> ineligible; all met -> eligible; else needs info."""
    results = tuple(evaluate_criterion(c, facts, as_of) for c in criteria)
    questions = _unique_questions(
        r.question for r in results if r.outcome is Outcome.UNKNOWN
    )
    if not results:
        return EligibilityResult(
            Verdict.NEEDS_INFO,
            results,
            (
                Question(
                    "No eligibility requirements were found. Check the official page."
                ),
            ),
            "No requirements found.",
        )
    not_met = sum(r.outcome is Outcome.NOT_MET for r in results)
    unknown = sum(r.outcome is Outcome.UNKNOWN for r in results)
    if not_met:
        verdict = Verdict.INELIGIBLE
        summary = f"{not_met} requirement{'s' if not_met != 1 else ''} not met."
    elif unknown:
        verdict = Verdict.NEEDS_INFO
        summary = (
            f"{len(questions)} question{'s' if len(questions) != 1 else ''} to answer."
        )
    else:
        verdict = Verdict.ELIGIBLE
        summary = "You meet every listed requirement."
    return EligibilityResult(verdict, results, questions, summary)


def _unique_questions(questions: Any) -> tuple[Question, ...]:
    """One question per fact: GPA is asked once even if two criteria need it."""
    seen: set[str] = set()
    unique: list[Question] = []
    for q in questions:
        if q is None:
            continue
        key = q.fact_key or q.text
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return tuple(unique)

"""The eligibility engine (FR-E1-E3) and the priority score (FR-E5, FR-E6).

Pure functions: facts in, verdicts out. All values are fictional.
"""

from datetime import date
from typing import Any

import pytest

from app.modules.eligibility.engine import (
    CriterionInput,
    Outcome,
    Verdict,
    evaluate,
    evaluate_criterion,
)
from app.modules.eligibility.places import canonical_country, canonical_state
from app.modules.eligibility.scoring import ESTIMATE, LISTING, priority_score
from app.modules.profile.catalog import FactValue

AS_OF = date(2027, 3, 1)


def crit(
    kind: str, cid: int = 1, confirmation: bool | None = None, **params: Any
) -> CriterionInput:
    return CriterionInput(cid, kind, params, f"Quote for {kind}.", confirmation)


def outcome(c: CriterionInput, **facts: FactValue) -> Outcome:
    return evaluate_criterion(c, facts, AS_OF).outcome


MET, NOT_MET, UNKNOWN = Outcome.MET, Outcome.NOT_MET, Outcome.UNKNOWN


# --- GPA ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        ({"gpa": 3.5}, MET),
        ({"gpa": 3.0}, MET),  # the minimum itself counts
        ({"gpa": 2.99}, NOT_MET),
        ({}, UNKNOWN),
        ({"gpa": 3.5, "gpa_scale": 4.0}, MET),
        ({"gpa": 4.6}, UNKNOWN),  # above 4.0 with no scale: weighted? ask
        ({"gpa": 4.6, "gpa_scale": 5.0}, MET),  # same number scale-less criterion
    ],
)
def test_gpa_min(facts: dict[str, FactValue], expected: Outcome) -> None:
    assert outcome(crit("gpa_min", min=3.0), **facts) is expected


def test_gpa_on_different_scales_is_never_guessed() -> None:
    result = evaluate_criterion(
        crit("gpa_min", min=4.0, scale=5.0), {"gpa": 3.6, "gpa_scale": 4.0}, AS_OF
    )

    assert result.outcome is UNKNOWN
    assert result.question is not None and "5 scale" in result.question.text


# --- Choices and flags ------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "fact", "values", "value", "expected"),
    [
        (
            "education_level_in",
            "education_level",
            ["undergraduate"],
            "undergraduate",
            MET,
        ),
        (
            "education_level_in",
            "education_level",
            ["undergraduate"],
            "graduate",
            NOT_MET,
        ),
        (
            "citizenship_in",
            "citizenship_status",
            ["us_citizen", "permanent_resident"],
            "daca",
            NOT_MET,
        ),
        ("enrollment_status_in", "enrollment_status", ["full_time"], "full_time", MET),
    ],
)
def test_choice_criteria(
    kind: str, fact: str, values: list[str], value: str, expected: Outcome
) -> None:
    assert outcome(crit(kind, values=values), **{fact: value}) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(["asian", "white"], MET), (["white"], NOT_MET), ([], NOT_MET)],
)
def test_multi_choice_needs_any_overlap(value: list[str], expected: Outcome) -> None:
    c = crit("race_ethnicity_in", values=["asian", "hispanic_or_latino"])

    assert outcome(c, race_ethnicity=value) is expected


@pytest.mark.parametrize(("value", "expected"), [(True, MET), (False, NOT_MET)])
def test_flags(value: bool, expected: Outcome) -> None:
    assert outcome(crit("first_generation"), first_generation=value) is expected


def test_missing_sensitive_fact_asks_an_optional_question() -> None:
    result = evaluate_criterion(
        crit("citizenship_in", values=["us_citizen"]), {}, AS_OF
    )

    assert result.outcome is UNKNOWN
    assert result.question is not None
    assert result.question.fact_key == "citizenship_status"
    assert result.question.optional is True  # FR-P6: never required


# --- Numbers and age ----------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "year", "expected"),
    [
        ({"min": 2027, "max": 2029}, 2028, MET),
        ({"min": 2027, "max": 2029}, 2030, NOT_MET),
        ({"max": 2027}, 2027, MET),
    ],
)
def test_grad_year(params: dict[str, int], year: int, expected: Outcome) -> None:
    assert (
        outcome(
            CriterionInput(1, "grad_year_between", params, "Graduation year rule."),
            expected_graduation_year=year,
        )
        is expected
    )


def test_income_and_service_hours() -> None:
    assert (
        outcome(crit("household_income_max", max=60000), household_income=60000) is MET
    )
    assert (
        outcome(crit("household_income_max", max=60000), household_income=60001)
        is NOT_MET
    )
    assert (
        outcome(crit("community_service_min", min=50), community_service_hours=49)
        is NOT_MET
    )


@pytest.mark.parametrize(
    ("born", "expected"),
    [
        ("2003-03-02", MET),  # 23 on the deadline (Mar 1, 2027)
        ("2002-03-02", MET),  # turns 25 the day after: still 24
        ("2002-03-01", NOT_MET),  # turns 25 exactly on the deadline: too old
        ("2010-03-02", NOT_MET),  # 16 on the deadline: too young
    ],
)
def test_age_is_checked_on_the_as_of_date(born: str, expected: Outcome) -> None:
    c = crit("age_between", min=17, max=24)

    assert outcome(c, date_of_birth=born) is expected


# --- Places and majors: unknown, never a guessed "not met" -------------------


@pytest.mark.parametrize(
    ("values", "state", "expected"),
    [
        (["Ohio", "Michigan"], "OH", MET),
        (["OH", "MI"], "Ohio", MET),
        (["Ohio"], "Texas", NOT_MET),  # both recognized: certain
        (["Ohio"], "Ohoi", UNKNOWN),  # typo: don't guess
        (["Ohio", "the Great Lakes region"], "Texas", UNKNOWN),  # unrecognized value
    ],
)
def test_states(values: list[str], state: str, expected: Outcome) -> None:
    assert (
        outcome(crit("state_in", values=values), state_of_residence=state) is expected
    )


@pytest.mark.parametrize(
    ("values", "country", "expected"),
    [
        (["United States"], "USA", MET),
        (["United States"], "Canada", UNKNOWN),  # only a match is certain
    ],
)
def test_countries(values: list[str], country: str, expected: Outcome) -> None:
    assert (
        outcome(crit("country_in", values=values), country_of_residence=country)
        is expected
    )


@pytest.mark.parametrize(
    ("major", "expected"),
    [
        ("Computer Science", MET),
        ("computer science and math", MET),  # contains a listed field
        ("Biology", UNKNOWN),  # may still count as STEM: ask, don't exclude
    ],
)
def test_majors_are_never_excluded_by_word_matching(
    major: str, expected: Outcome
) -> None:
    c = crit("major_in", values=["Computer Science", "Engineering"])

    assert outcome(c, major=major) is expected


def test_place_helpers() -> None:
    assert canonical_state("state of new york") == "New York"
    assert canonical_state("Washington DC") == "District of Columbia"
    assert canonical_state("Atlantis") is None
    assert canonical_country("The United States of America") == "united states"


# --- Free text (FR-E3) --------------------------------------------------------


@pytest.mark.parametrize(
    ("confirmation", "expected"), [(None, UNKNOWN), (True, MET), (False, NOT_MET)]
)
def test_free_text_follows_the_students_answer(
    confirmation: bool | None, expected: Outcome
) -> None:
    assert outcome(crit("free_text", confirmation=confirmation)) is expected


def test_uninterpretable_stored_criterion_asks_instead_of_crashing() -> None:
    broken = CriterionInput(1, "gpa_min", {"min": "three"}, "GPA three or more.")

    assert outcome(broken, gpa=3.5) is UNKNOWN


# --- Verdicts (FR-E2) --------------------------------------------------------


def test_any_not_met_means_ineligible() -> None:
    criteria = [crit("gpa_min", 1, min=3.0), crit("first_generation", 2)]

    result = evaluate(criteria, {"gpa": 2.5}, AS_OF)

    assert result.verdict is Verdict.INELIGIBLE


def test_all_met_means_eligible() -> None:
    criteria = [crit("gpa_min", 1, min=3.0), crit("first_generation", 2)]

    result = evaluate(criteria, {"gpa": 3.5, "first_generation": True}, AS_OF)

    assert result.verdict is Verdict.ELIGIBLE
    assert not result.questions


def test_unknowns_give_needs_info_with_one_question_per_fact() -> None:
    criteria = [
        crit("gpa_min", 1, min=3.0),
        crit("gpa_min", 2, min=2.5),  # needs GPA too: asked once
        crit("free_text", 3),
    ]

    result = evaluate(criteria, {}, AS_OF)

    assert result.verdict is Verdict.NEEDS_INFO
    assert [q.fact_key for q in result.questions] == ["gpa", None]
    assert result.summary == "2 questions to answer."


def test_no_criteria_is_not_called_eligible() -> None:
    result = evaluate([], {}, AS_OF)

    assert result.verdict is Verdict.NEEDS_INFO
    assert "No eligibility requirements" in result.questions[0].text


def test_same_inputs_same_verdict() -> None:
    criteria = [crit("gpa_min", 1, min=3.0), crit("state_in", 2, values=["Ohio"])]
    facts: dict[str, FactValue] = {"gpa": 3.2, "state_of_residence": "OH"}

    assert evaluate(criteria, facts, AS_OF) == evaluate(criteria, facts, AS_OF)


# --- Priority score (FR-E5, FR-E6) ----------------------------------------


TODAY = date(2027, 1, 15)


def test_score_parts_are_labeled_listing_or_estimate() -> None:
    result = evaluate([crit("gpa_min", min=3.0)], {"gpa": 3.5}, AS_OF)

    score = priority_score(result, amount=2500, deadline=date(2027, 2, 20), today=TODAY)

    bases = {p.name: p.basis for p in score.parts}
    assert bases == {
        "eligibility": LISTING,
        "amount": LISTING,
        "deadline": LISTING,
        "fit": ESTIMATE,
        "effort": ESTIMATE,
    }
    assert 0 < score.total <= 100
    assert "not your chances" in score.note  # FR-E6: never presented as odds


def test_unpublished_amount_and_deadline_are_estimates() -> None:
    result = evaluate([crit("gpa_min", min=3.0)], {"gpa": 3.5}, AS_OF)

    score = priority_score(result, amount=None, deadline=None, today=TODAY)

    parts = {p.name: p for p in score.parts}
    assert parts["amount"].basis == ESTIMATE and parts["deadline"].basis == ESTIMATE


def test_past_deadline_or_ineligible_scores_zero() -> None:
    eligible = evaluate([crit("gpa_min", min=3.0)], {"gpa": 3.5}, AS_OF)
    ineligible = evaluate([crit("gpa_min", min=3.0)], {"gpa": 2.0}, AS_OF)

    assert (
        priority_score(
            eligible, amount=5000, deadline=date(2027, 1, 1), today=TODAY
        ).total
        == 0
    )
    assert (
        priority_score(
            ineligible, amount=5000, deadline=date(2027, 3, 1), today=TODAY
        ).total
        == 0
    )


def test_bigger_awards_rank_higher_all_else_equal() -> None:
    result = evaluate([crit("gpa_min", min=3.0)], {"gpa": 3.5}, AS_OF)
    deadline = date(2027, 2, 20)

    small = priority_score(result, amount=500, deadline=deadline, today=TODAY)
    large = priority_score(result, amount=10000, deadline=deadline, today=TODAY)

    assert large.total > small.total


def test_warning_signs_push_a_listing_down_but_keep_it() -> None:
    result = evaluate([crit("gpa_min", min=3.0)], {"gpa": 3.5}, AS_OF)
    deadline = date(2027, 2, 20)

    clean = priority_score(result, amount=5000, deadline=deadline, today=TODAY)
    flagged = priority_score(
        result, amount=5000, deadline=deadline, today=TODAY, warning_signs=2
    )

    assert 0 < flagged.total < clean.total / 2  # shown, but not recommended first
    assert "warning signs" in flagged.note

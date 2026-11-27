"""A priority score to sort scholarships (FR-E5), with honest labels (FR-E6).

This is our ranking of where to spend effort, not the student's chances of
winning: no acceptance rates or odds are ever shown, because sponsors rarely
publish them and inventing them would be misleading.

Every part says what it's based on:
  * "listing": the sponsor's published amount or deadline, or the
    eligibility verdict computed from the listing and the student's profile.
  * "estimate": our own heuristic (fit and effort), labeled as such.
"""

import math
from dataclasses import dataclass
from datetime import date

from app.modules.eligibility.engine import EligibilityResult, Outcome, Verdict

LISTING = "listing"
ESTIMATE = "estimate"

WEIGHTS = {
    "eligibility": 0.35,
    "amount": 0.20,
    "deadline": 0.20,
    "fit": 0.15,
    "effort": 0.10,
}


@dataclass(frozen=True)
class ScorePart:
    """One ingredient of the score (0-1), and what it's based on."""

    name: str
    value: float
    basis: str  # LISTING or ESTIMATE
    detail: str


@dataclass(frozen=True)
class PriorityScore:
    """0-100, higher = worth looking at sooner. Not a probability."""

    total: int
    parts: tuple[ScorePart, ...]
    note: str = "Our ranking for where to spend effort, not your chances of winning."


def priority_score(
    result: EligibilityResult,
    *,
    amount: int | None,
    deadline: date | None,
    today: date,
) -> PriorityScore:
    parts = (
        _eligibility(result),
        _amount(amount),
        _deadline(deadline, today),
        _fit(result),
        _effort(result),
    )
    if deadline is not None and deadline < today:
        return PriorityScore(0, parts, "The deadline has passed.")
    if result.verdict is Verdict.INELIGIBLE:
        return PriorityScore(0, parts, "You don't meet a listed requirement.")
    total = round(100 * sum(WEIGHTS[p.name] * p.value for p in parts))
    return PriorityScore(total, parts)


def _eligibility(result: EligibilityResult) -> ScorePart:
    value = {Verdict.ELIGIBLE: 1.0, Verdict.NEEDS_INFO: 0.5, Verdict.INELIGIBLE: 0.0}
    return ScorePart("eligibility", value[result.verdict], LISTING, result.summary)


def _amount(amount: int | None) -> ScorePart:
    if not amount:
        return ScorePart("amount", 0.3, ESTIMATE, "Amount not published.")
    # $100 -> 0.5, $1,000 -> 0.75, $10,000+ -> 1.0
    value = max(0.0, min(1.0, math.log10(amount) / 4))
    return ScorePart("amount", value, LISTING, f"${amount:,} published by the sponsor.")


def _deadline(deadline: date | None, today: date) -> ScorePart:
    if deadline is None:
        return ScorePart("deadline", 0.5, ESTIMATE, "Deadline not published.")
    days = (deadline - today).days
    if days < 0:
        return ScorePart("deadline", 0.0, LISTING, "The deadline has passed.")
    if days < 7:
        value, detail = 0.4, f"Due in {days} day{'s' if days != 1 else ''}: tight."
    elif days <= 60:
        value, detail = 1.0, f"Due in {days} days: a good window."
    else:
        value, detail = 0.7, f"Due in {days} days: no rush yet."
    return ScorePart("deadline", value, LISTING, detail)


def _fit(result: EligibilityResult) -> ScorePart:
    if not result.results:
        return ScorePart("fit", 0.5, ESTIMATE, "No requirements to compare.")
    met = sum(r.outcome is Outcome.MET for r in result.results)
    value = met / len(result.results)
    return ScorePart(
        "fit", value, ESTIMATE, f"{met} of {len(result.results)} confirmed."
    )


def _effort(result: EligibilityResult) -> ScorePart:
    open_items = len(result.questions)
    value = max(0.0, 1.0 - 0.15 * open_items)
    detail = (
        "Nothing left to answer."
        if not open_items
        else f"{open_items} open question{'s' if open_items != 1 else ''}."
    )
    return ScorePart("effort", value, ESTIMATE, detail)

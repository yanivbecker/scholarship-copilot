"""Possible duplicates and merging them on request (FR-D6).

Automatic merging only happens for near-certain matches (dedup.py). Anything
less certain is listed here for the student to decide.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.eligibility.models import CriterionConfirmation
from app.modules.scholarships import service
from app.modules.scholarships.dedup import Candidate, possible_duplicate_score
from app.modules.scholarships.models import Scholarship


class MergeError(ValueError):
    """The merge doesn't make sense. User-facing."""


@dataclass(frozen=True)
class PossibleDuplicate:
    """Two stored scholarships that may be the same one."""

    first: Scholarship
    second: Scholarship
    score: float


def _candidate(s: Scholarship) -> Candidate:
    return Candidate(s.name, s.sponsor, s.official_url)


def possible_duplicates(session: Session, user_id: int) -> list[PossibleDuplicate]:
    items = service.list_scholarships(session, user_id)
    pairs: list[PossibleDuplicate] = []
    for i, first in enumerate(items):
        for second in items[i + 1 :]:
            score = possible_duplicate_score(_candidate(first), _candidate(second))
            if score is not None:
                pairs.append(PossibleDuplicate(first, second, score))
    return sorted(pairs, key=lambda p: -p.score)


def merge_scholarships(
    session: Session, user_id: int, keep_id: int, merge_id: int
) -> Scholarship:
    """Move everything from `merge_id` into `keep_id`, then delete `merge_id`.

    Per year, the more recently extracted cycle wins. The student's own
    confirmations are kept (the kept scholarship's answer wins a conflict).
    """
    if keep_id == merge_id:
        raise MergeError("Choose two different scholarships to merge.")
    keep = service.get_scholarship(session, user_id, keep_id)
    other = service.get_scholarship(session, user_id, merge_id)

    years = {c.year: c for c in keep.cycles}
    for cycle in list(other.cycles):
        mine = years.get(cycle.year)
        if mine is None or cycle.extracted_at > mine.extracted_at:
            if mine is not None:
                keep.cycles.remove(mine)
            other.cycles.remove(cycle)
            keep.cycles.append(cycle)
            years[cycle.year] = cycle

    for confirmation in session.scalars(
        select(CriterionConfirmation).where(
            CriterionConfirmation.user_id == user_id,
            CriterionConfirmation.scholarship_id == other.id,
        )
    ):
        clash = session.scalars(
            select(CriterionConfirmation).where(
                CriterionConfirmation.user_id == user_id,
                CriterionConfirmation.scholarship_id == keep.id,
                CriterionConfirmation.quote_key == confirmation.quote_key,
            )
        ).first()
        if clash is None:
            confirmation.scholarship_id = keep.id
        else:
            session.delete(confirmation)

    keep.sponsor = keep.sponsor or other.sponsor
    keep.official_url = keep.official_url or other.official_url
    keep.description = keep.description or other.description
    known = {f["signal"] for f in keep.scam_flags}
    keep.scam_flags = keep.scam_flags + [
        f for f in other.scam_flags if f["signal"] not in known
    ]
    if other.needs_review and not keep.needs_review:
        keep.needs_review, keep.review_reason = True, other.review_reason
    session.flush()
    session.delete(other)
    session.flush()
    return keep

"""Recognizing the same scholarship found twice (FR-D6).

Merging two *different* scholarships would mix their criteria and produce
wrong verdicts, which is far worse than showing a duplicate. So:

* Automatic merge only when it's near-certain: the same official page, or
  near-identical names (after dropping generic words like "scholarship") with
  compatible sponsors.
* Lower similarity is reported as a "possible duplicate" for the student to
  merge (or not) themselves.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz

from app.modules.scholarships.evidence import normalize_for_matching

AUTO_MERGE_NAME = 95  # token_sort: same words, maybe reordered or retyped
POSSIBLE_DUPLICATE_NAME = 70
SPONSOR_COMPATIBLE = 85
SAME_URL_SUBSET = 90  # token_set: one name contains the other

# Words that say "this is a scholarship" rather than which one it is.
GENERIC_WORDS = frozenset(
    "the a an of for and in to scholarship scholarships award awards program "
    "programs fund grant grants prize fellowship".split()
)


@dataclass(frozen=True)
class Candidate:
    """The identifying parts of a scholarship."""

    name: str
    sponsor: str | None
    official_url: str | None


def name_key(name: str) -> str:
    """ "The Test Foundation STEM Scholarship" -> "test foundation stem"."""
    words = normalize_for_matching(name).replace("-", " ").split()
    meaningful = [w.strip(".,:;'\"()") for w in words if w not in GENERIC_WORDS]
    return " ".join(w for w in meaningful if w) or normalize_for_matching(name)


def name_similarity(a: str, b: str) -> float:
    """0-100: how similar the full names are; word order doesn't matter."""
    return float(fuzz.token_sort_ratio(name_key(a), name_key(b)))


def _subset_similarity(a: str, b: str) -> float:
    """0-100: 100 when one name's words are all in the other."""
    return float(fuzz.token_set_ratio(name_key(a), name_key(b)))


def _shorter_has_two_words(a: str, b: str) -> bool:
    # "stem" is contained in "stem nursing" but says too little on its own.
    return min(len(name_key(a).split()), len(name_key(b).split())) >= 2


def _sponsors_compatible(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True  # one listing didn't name the sponsor: no conflict
    return fuzz.token_sort_ratio(name_key(a), name_key(b)) >= SPONSOR_COMPATIBLE


def is_same_scholarship(new: Candidate, existing: Candidate) -> bool:
    """Near-certain match: safe to merge automatically."""
    if not _sponsors_compatible(new.sponsor, existing.sponsor):
        return False
    if new.official_url and new.official_url == existing.official_url:
        # The same page is strong evidence; the names just need to overlap.
        return _subset_similarity(new.name, existing.name) >= SAME_URL_SUBSET
    return name_similarity(new.name, existing.name) >= AUTO_MERGE_NAME


def possible_duplicate_score(a: Candidate, b: Candidate) -> float | None:
    """Similarity if the pair is worth showing the student, else None."""
    if not _sponsors_compatible(a.sponsor, b.sponsor):
        return None
    similarity = name_similarity(a.name, b.name)
    if similarity >= POSSIBLE_DUPLICATE_NAME:
        return similarity
    if _subset_similarity(a.name, b.name) == 100 and _shorter_has_two_words(
        a.name, b.name
    ):
        return float(POSSIBLE_DUPLICATE_NAME)
    return None

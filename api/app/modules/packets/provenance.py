"""Where writing comes from, and whether its claims can be traced (FR-A5).

CLAUDE.md: "Never fabricate student experiences. Writing help draws only from
profile facts and the story bank."

Two pieces live here, both deterministic (no AI):

* `Material`: the facts and stories the student chose to share with the AI
  for one request. Only what they tick is ever sent (see writing.py).
* `check_claims`: finds the *specific* claims in a text (numbers, and names
  written with capital letters) and reports any that don't appear in the
  student's facts or stories. A number or a name is the kind of detail an AI
  invents most easily and a reader trusts most, so it's what we check.

The check can't understand meaning; it highlights things for the student to
look at. For AI drafts, writing.py additionally requires every sentence to
cite the facts or story quotes it is built from.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.profile import repository as profile_repo
from app.modules.profile.catalog import FactValidationError, choice_label
from app.modules.profile.catalog import get_definition
from app.modules.profile.models import ProfileFact, Story
from app.modules.scholarships.evidence import normalize_for_matching

# 3.8 / 2,500 / $1,000 / 40% / 2027 (not parts of words like "STEM2").
_NUMBER = re.compile(r"(?<![\w.])\$?(\d[\d,]*(?:\.\d+)?)%?(?![\w])")
# A run of capitalized words: "Lincoln High School", "Ohio", "FIRST Robotics".
_NAME = re.compile(r"\b[A-Z][\w'&.-]*(?:\s+(?:of|the|and|for|de|[A-Z][\w'&.-]*))*")
# Capitalized because of grammar, not because they're names.
_NOT_NAMES = frozenset({"i", "i'm", "i've", "i'd", "i'll"})
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


class MaterialError(ValueError):
    """A chosen fact or story doesn't exist. The message is user-facing."""


def fact_text(fact: ProfileFact) -> str:
    """ "GPA: 3.8", "State of residence: Ohio" — how a fact reads in a prompt."""
    label, shown = fact_parts(fact)
    return f"{label}: {shown}"


def fact_parts(fact: ProfileFact) -> tuple[str, str]:
    """(label, value as a person would write it), e.g. ("GPA", "3.8")."""
    try:
        definition = get_definition(fact.key)
        label, has_choices = definition.label, bool(definition.choices)
    except FactValidationError:  # a custom, scholarship-specific fact
        label, has_choices = fact.label or fact.key, False
    value = fact.value
    if isinstance(value, list):
        shown = ", ".join(choice_label(v) if has_choices else str(v) for v in value)
    elif isinstance(value, bool):
        shown = "yes" if value else "no"
    elif isinstance(value, float):
        shown = f"{value:g}"
    elif isinstance(value, str) and has_choices:
        shown = choice_label(value)
    else:
        shown = str(value)
    return label, shown


@dataclass(frozen=True)
class Material:
    """Facts (key -> readable text) and stories the student chose to use."""

    facts: dict[str, str]
    stories: dict[int, Story]

    def text(self) -> str:
        """Everything, as one block of text, for the claim check."""
        parts = list(self.facts.values())
        for story in self.stories.values():
            parts += [story.title, story.body]
        return "\n".join(parts)


def gather_material(
    session: Session,
    user_id: int,
    *,
    fact_keys: Iterable[str] | None = None,
    story_ids: Iterable[int] | None = None,
) -> Material:
    """The student's chosen facts and stories. `None` means "all of them"
    (used only for the local claim check, never for an AI request)."""
    facts = {f.key: f for f in profile_repo.list_facts(session, user_id)}
    stories = {s.id: s for s in profile_repo.list_stories(session, user_id)}
    if fact_keys is not None:
        wanted_keys = list(dict.fromkeys(fact_keys))
        unknown = [k for k in wanted_keys if k not in facts]
        if unknown:
            raise MaterialError(f"These facts aren't in your profile: {unknown}.")
        facts = {k: facts[k] for k in wanted_keys}
    if story_ids is not None:
        wanted_ids = list(dict.fromkeys(story_ids))
        if any(i not in stories for i in wanted_ids):
            raise MaterialError("One of the chosen stories isn't in your story bank.")
        stories = {i: stories[i] for i in wanted_ids}
    return Material({k: fact_text(f) for k, f in facts.items()}, stories)


# --- The claim check -----------------------------------------------------------


def sentences(text: str) -> list[str]:
    return [" ".join(s.split()) for s in _SENTENCE.split(text) if s.strip()]


def _numbers(text: str) -> set[float]:
    found = set()
    for match in _NUMBER.finditer(text):
        try:
            found.add(float(match.group(1).replace(",", "")))
        except ValueError:  # e.g. "1,2,3" isn't one number
            continue
    return found


def claims_in(sentence: str) -> list[str]:
    """The specific details in a sentence: numbers and capitalized names."""
    found = [m.group(0) for m in _NUMBER.finditer(sentence)]
    for match in _NAME.finditer(sentence):
        name = match.group(0).rstrip(".")
        first_word = match.start() == 0 or sentence[: match.start()].rstrip()[-1:] in {
            ":",
            '"',
        }
        words = name.split()
        if first_word:
            words = words[1:]  # "My", "When", "Our": capitalized by grammar
            while words and words[0][0].islower():
                words = words[1:]
        # "of"/"and" may join a name ("Bank of America") but never end one.
        while words and words[-1][0].islower():
            words = words[:-1]
        if not words or (len(words) == 1 and words[0].lower() in _NOT_NAMES):
            continue
        found.append(" ".join(words))
    return found


def unsupported_claims(sentence: str, material_text: str) -> list[str]:
    """Claims in `sentence` that the material doesn't contain."""
    haystack = normalize_for_matching(material_text)
    known_numbers = _numbers(material_text)
    missing = []
    for claim in claims_in(sentence):
        if _NUMBER.fullmatch(claim):
            if not _numbers(claim) <= known_numbers:
                missing.append(claim)
        elif normalize_for_matching(claim) not in haystack:
            missing.append(claim)
    return missing


@dataclass(frozen=True)
class SentenceCheck:
    """One sentence and the claims in it we couldn't trace."""

    sentence: str
    unsupported: tuple[str, ...]


def check_claims(text: str, material: Material) -> list[SentenceCheck]:
    """FR-A5: every sentence, with the claims we couldn't trace."""
    source = material.text()
    return [
        SentenceCheck(s, tuple(unsupported_claims(s, source))) for s in sentences(text)
    ]

"""Scholarship and criteria extraction from page text (FR-D5, FR-D8, FR-D9).

The AI proposes; code decides what to keep:

* A scholarship is kept only if its name appears in the page.
* A criterion is kept only if its quote appears verbatim in the page
  (evidence.py). Criteria without a matching quote are rejected and counted.
* A criterion whose parameters don't fit its kind becomes free text, so the
  requirement isn't lost and never gets a made-up interpretation.
* Amount and deadline are kept only when their quoted wording is in the page
  and agrees with the numbers.

Nothing the AI returns is trusted just because it parsed.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.ai.prompting import UNTRUSTED_DATA_RULES, wrap_untrusted
from app.modules.profile.catalog import CATALOG
from app.modules.scholarships.criteria import (
    CHOICE_KINDS,
    CriterionKind,
    CriterionParamError,
    RawCriterion,
    clean_params,
)
from app.modules.scholarships.evidence import SourceText, normalize_for_matching
from app.modules.sources.url_safety import UnsafeURLError, normalize_source_url

MAX_SCHOLARSHIPS_PER_PAGE = 50
MAX_CRITERIA_PER_SCHOLARSHIP = 40
MAX_NAME = 300
MAX_DESCRIPTION = 2000
MIN_NAME_CHARS = 4

# --- What the AI must return (validated by Pydantic, see ai/structured.py) ---


class _Strict(BaseModel):
    # Unknown fields mean the answer isn't what we asked for: reject it rather
    # than quietly ignoring part of it.
    model_config = ConfigDict(extra="forbid")


class ExtractedCriterion(_Strict):
    """One eligibility requirement as the AI found it."""

    kind: CriterionKind = Field(
        description="The kind of requirement; free_text if unsure."
    )
    quote: str = Field(
        description="The exact sentence(s) from the page stating this "
        "requirement, copied character for character."
    )
    min_number: float | None = Field(default=None, description="Lower bound, if any.")
    max_number: float | None = Field(default=None, description="Upper bound, if any.")
    scale: float | None = Field(default=None, description="GPA scale, e.g. 4.0.")
    values: list[str] = Field(default_factory=list, description="Allowed values.")


class ExtractedScholarship(_Strict):
    """One scholarship listed on the page."""

    name: str = Field(description="The scholarship's name exactly as written.")
    sponsor: str | None = Field(default=None, description="Organization offering it.")
    official_url: str | None = Field(default=None, description="Its own page URL.")
    description: str | None = Field(default=None, description="One or two sentences.")
    amount_text: str | None = Field(
        default=None, description="The award amount exactly as written."
    )
    amount_min_usd: int | None = None
    amount_max_usd: int | None = None
    deadline: str | None = Field(default=None, description="YYYY-MM-DD.")
    deadline_quote: str | None = Field(
        default=None, description="The exact words stating the deadline."
    )
    cycle_year: int | None = Field(default=None, description="Award year, if stated.")
    criteria: list[ExtractedCriterion] = Field(default_factory=list)


class ExtractionOutput(_Strict):
    """Everything found on one page. An empty list if it lists none.

    Required (no default): an answer without this field is invalid, not
    "nothing found".
    """

    scholarships: list[ExtractedScholarship]


# --- The prompt -----------------------------------------------------------


def _kind_guide() -> str:
    lines = [
        "- gpa_min: minimum GPA in min_number; GPA scale in scale if stated.",
        "- grad_year_between: graduation year bounds in min_number/max_number.",
        "- age_between: age bounds in years in min_number/max_number.",
        "- household_income_max: maximum household income (USD) in max_number.",
        "- community_service_min: minimum volunteer hours in min_number.",
        "- state_in / country_in / major_in: allowed values in values, as written.",
        "- first_generation, pell_eligible, has_disability: no parameters.",
    ]
    for kind, fact_key in CHOICE_KINDS.items():
        allowed = ", ".join(CATALOG[fact_key].choices)
        lines.append(f"- {kind.value}: values must be from: {allowed}.")
    lines.append(
        "- free_text: any other requirement (essays, leadership, financial "
        "need, membership, ...), or whenever a requirement doesn't fit a kind "
        "exactly. Prefer free_text over a guess."
    )
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You extract scholarship listings from one web page for a \
student's personal scholarship tracker.

Return every scholarship the page describes, with its eligibility \
requirements. Use only what the page says. Do not add knowledge from \
elsewhere, and do not guess: leave a field empty rather than invent it.

Rules for criteria:
- Each criterion needs a quote: the exact sentence(s) from the page, copied \
character for character. Paraphrased quotes are discarded.
- One requirement per criterion. Split combined requirements.
- Application materials (essays, letters, transcripts) are not eligibility \
criteria; include them only as free_text if the page makes them a condition.

Criterion kinds:
{_kind_guide()}

Amounts and deadlines: copy the wording into amount_text / deadline_quote, \
and give numbers only when the page states them clearly.

If the page lists no scholarships, return an empty list.

{UNTRUSTED_DATA_RULES}"""


def build_user_prompt(text: str, *, source_url: str, today: date) -> str:
    return (
        f"Today's date: {today.isoformat()}\n\n"
        + wrap_untrusted(text, source_url=source_url)
        + "\n\nExtract the scholarships from the page above."
    )


# --- Verifying what came back --------------------------------------------


@dataclass
class VerifiedCriterion:
    """A criterion whose quote was found in the source."""

    kind: CriterionKind
    params: dict[str, object]
    quote: str


@dataclass
class VerifiedScholarship:  # pylint: disable=too-many-instance-attributes
    """A scholarship that passed the checks, ready to save."""

    name: str
    sponsor: str | None
    official_url: str | None
    description: str | None
    year: int
    amount_text: str | None
    amount_min: int | None
    amount_max: int | None
    deadline: date | None
    deadline_quote: str | None
    criteria: list[VerifiedCriterion] = field(default_factory=list)
    rejected_criteria: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """What passed the checks, and how many scholarships were rejected."""

    scholarships: list[VerifiedScholarship]
    rejected_scholarships: int = 0


def verify(output: ExtractionOutput, *, text: str, today: date) -> VerificationResult:
    source = SourceText(text)
    normalized_text = normalize_for_matching(text)
    result = VerificationResult(scholarships=[])
    for item in output.scholarships[:MAX_SCHOLARSHIPS_PER_PAGE]:
        name = " ".join(item.name.split())[:MAX_NAME]
        name_key = normalize_for_matching(name)
        if len(name_key) < MIN_NAME_CHARS or name_key not in normalized_text:
            result.rejected_scholarships += 1  # not on the page: likely invented
            continue
        result.scholarships.append(_verify_one(item, name, source, today))
    return result


def _verify_one(
    item: ExtractedScholarship, name: str, source: SourceText, today: date
) -> VerifiedScholarship:
    notes: list[str] = []
    amount_text, amount_min, amount_max = _verify_amount(item, source, notes)
    deadline, deadline_quote = _verify_deadline(item, source, notes)
    scholarship = VerifiedScholarship(
        name=name,
        sponsor=_clean(item.sponsor, MAX_NAME),
        official_url=_safe_url(item.official_url),
        description=_clean(item.description, MAX_DESCRIPTION),
        year=_cycle_year(item, deadline, today),
        amount_text=amount_text,
        amount_min=amount_min,
        amount_max=amount_max,
        deadline=deadline,
        deadline_quote=deadline_quote,
        notes=notes,
    )
    scholarship.criteria, scholarship.rejected_criteria = _verify_criteria(item, source)
    return scholarship


def _verify_criteria(
    item: ExtractedScholarship, source: SourceText
) -> tuple[list[VerifiedCriterion], int]:
    """Keep criteria whose quote is on the page; count the rest (FR-D5)."""
    kept: list[VerifiedCriterion] = []
    rejected = 0
    seen: set[tuple[str, str]] = set()
    for extracted in item.criteria[:MAX_CRITERIA_PER_SCHOLARSHIP]:
        quote = " ".join(extracted.quote.split())
        if not source.contains_quote(quote):
            rejected += 1  # no verbatim quote, no criterion
            continue
        raw = RawCriterion(
            kind=extracted.kind.value,
            quote=quote,
            min_number=extracted.min_number,
            max_number=extracted.max_number,
            scale=extracted.scale,
            values=tuple(extracted.values),
        )
        try:
            kind, params = clean_params(raw)
        except CriterionParamError:
            kind, params = CriterionKind.FREE_TEXT, {}  # keep it, uninterpreted
        key = (kind.value, normalize_for_matching(quote))
        if key not in seen:
            seen.add(key)
            kept.append(VerifiedCriterion(kind, params, quote))
    return _drop_redundant_free_text(kept), rejected


def _drop_redundant_free_text(
    criteria: list[VerifiedCriterion],
) -> list[VerifiedCriterion]:
    """A free-text fallback for a sentence that a structured criterion already
    checks would only ask the student to confirm the same thing by hand."""
    structured = {
        normalize_for_matching(c.quote)
        for c in criteria
        if c.kind is not CriterionKind.FREE_TEXT
    }
    return [
        c
        for c in criteria
        if c.kind is not CriterionKind.FREE_TEXT
        or normalize_for_matching(c.quote) not in structured
    ]


def _verify_amount(
    item: ExtractedScholarship, source: SourceText, notes: list[str]
) -> tuple[str | None, int | None, int | None]:
    text = _clean(item.amount_text, 300)
    if text is None:
        return None, None, None
    if not source.contains_phrase(text):
        notes.append("The award amount wasn't found word for word on the page.")
        return None, None, None
    digits = re.sub(r"\D", "", text)

    def supported(value: int | None) -> int | None:
        # Keep a number only if its digits are in the quoted amount text.
        return value if value and value > 0 and str(value) in digits else None

    low, high = supported(item.amount_min_usd), supported(item.amount_max_usd)
    if low and high and low > high:
        low, high = None, None
    return text, low, high


def _verify_deadline(
    item: ExtractedScholarship, source: SourceText, notes: list[str]
) -> tuple[date | None, str | None]:
    if not item.deadline:
        return None, None
    try:
        deadline = date.fromisoformat(item.deadline)
    except ValueError:
        notes.append("The deadline wasn't a valid date.")
        return None, None
    quote = _clean(item.deadline_quote, 500)
    if quote is None or not source.contains_phrase(quote):
        notes.append("The deadline wasn't found word for word on the page.")
        return None, None
    if not _date_agrees(deadline, quote):
        notes.append("The deadline date didn't match the page's wording.")
        return None, None
    return deadline, quote


_MONTHS = (
    "january february march april may june july august september october "
    "november december"
).split()


def _date_agrees(value: date, quote: str) -> bool:
    """The quote must mention the day, and the month (by name or number)."""
    lowered = quote.lower()
    numbers = {int(n) for n in re.findall(r"\d+", lowered)}
    if value.day not in numbers:
        return False
    month = _MONTHS[value.month - 1]
    month_named = month[:3] in lowered
    years = {n for n in numbers if n > 1900}
    if years and value.year not in years:
        return False
    return month_named or value.month in numbers


def _cycle_year(item: ExtractedScholarship, deadline: date | None, today: date) -> int:
    if deadline is not None:
        return deadline.year
    if item.cycle_year and today.year - 1 <= item.cycle_year <= today.year + 3:
        return item.cycle_year
    return today.year


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())[:limit]
    return cleaned or None


def _safe_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return normalize_source_url(url)
    except UnsafeURLError:
        return None

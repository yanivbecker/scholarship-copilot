"""The AI-use rules check (FR-A1, FR-A2).

CLAUDE.md: "AI-policy check before any writing help. Unclear rules count as
no AI writing." So:

1. Code scans the scholarship's own source text for sentences about AI
   tools, "your own work", plagiarism or outside help, and suggests a reading
   (allowed / prohibited / unclear) from their wording. No mention = unclear.
2. The student reads those sentences and confirms the result (FR-A2).
3. "Allowed" needs evidence: a quote that appears verbatim in the source.
4. AI drafting is on only when the confirmed result is ALLOWED; anything
   else, including "not checked", means off. Coaching (which never writes
   the answer) is off only when the rules are confirmed as PROHIBITED.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.packets.models import Packet, RulesStatus
from app.modules.scholarships.evidence import SourceText
from app.modules.scholarships.models import ScholarshipCycle
from app.modules.sources.models import PageSnapshot
from app.modules.tracking.models import AuditEvent

MAX_CANDIDATES = 10
RULES_CONFIRMED = "rules_confirmed"

_AI_TERMS = re.compile(
    r"\b(AI|A\.I\.|artificial intelligence|ChatGPT|GPT(-?\d+)?|generative|"
    r"large language models?|LLMs?|chatbots?|Copilot|Gemini|"
    r"(AI|automated) writing tools?)\b",
    re.IGNORECASE,
)
# Shown to the student for context, but never used to suggest a reading.
_HONESTY_TERMS = re.compile(
    r"\b(own (original )?work|written (solely|entirely) by|plagiari\w+|"
    r"outside (help|assistance)|ghost-?writ\w*)\b",
    re.IGNORECASE,
)
_PROHIBITS = re.compile(
    r"\b(not (be )?(permitted|allowed|accepted|acceptable)|prohibited|"
    r"must not|may not|cannot|can't|forbidden|disqualif\w+|banned|"
    r"no use of|do not use|don't use)\b",
    re.IGNORECASE,
)
_RESTRICTS = re.compile(
    r"\b(own (original )?work|written by you|solely|entirely|only for|but)\b",
    re.IGNORECASE,
)
_ALLOWS = re.compile(
    r"\b(may use|(are|is) (permitted|allowed|welcome) to use|"
    r"(is|are) (permitted|allowed)|you can use|welcome to use|allowed for)\b",
    re.IGNORECASE,
)


class RulesError(ValueError):
    """The rules confirmation isn't valid. The message is user-facing."""


def ai_coaching_allowed(packet: Packet) -> bool:
    """Coaching never writes the answer, so only a confirmed ban turns it off."""
    return packet.rules_status is not RulesStatus.PROHIBITED


def ai_writing_allowed(packet: Packet) -> bool:
    """Drafting writes text: only with rules confirmed as allowing it."""
    return (
        packet.rules_status is RulesStatus.ALLOWED
        and packet.rules_confirmed_at is not None
    )


@dataclass(frozen=True)
class RulesScan:
    """What the code found, for the student to confirm."""

    suggested: RulesStatus
    candidates: tuple[str, ...]
    source_url: str | None
    has_text: bool


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [" ".join(c.split()) for c in chunks if c.strip()]


def suggest_status(candidates: list[str]) -> RulesStatus:
    """A starting point for the student, never the decision itself.

    Only sentences that mention AI count. A clear ban suggests prohibited; a
    clear permission with no conditions suggests allowed; a permission with
    conditions ("for brainstorming, but...") or no AI sentence at all
    suggests unclear, because silence or nuance is not permission.
    """
    about_ai = [c for c in candidates if _AI_TERMS.search(c)]
    allows = any(_ALLOWS.search(c) for c in about_ai)
    prohibits = any(_PROHIBITS.search(c) for c in about_ai)
    restricts = any(_RESTRICTS.search(c) for c in about_ai)
    if prohibits and not allows:
        return RulesStatus.PROHIBITED
    if allows and not (prohibits or restricts):
        return RulesStatus.ALLOWED
    return RulesStatus.UNCLEAR


def find_policy_sentences(text: str) -> list[str]:
    found = [
        s for s in _sentences(text) if _AI_TERMS.search(s) or _HONESTY_TERMS.search(s)
    ]
    return list(dict.fromkeys(found))[:MAX_CANDIDATES]


def _source_text(session: Session, packet: Packet) -> tuple[str | None, str | None]:
    cycle = session.get(ScholarshipCycle, packet.cycle_id)
    if cycle is None or cycle.source_id is None:
        return None, cycle.source_url if cycle else None
    snapshot = session.scalars(
        select(PageSnapshot)
        .where(PageSnapshot.source_id == cycle.source_id)
        .order_by(PageSnapshot.fetched_at.desc(), PageSnapshot.id.desc())
    ).first()
    return (snapshot.text if snapshot else None), cycle.source_url


def scan_rules(session: Session, packet: Packet) -> RulesScan:
    text, url = _source_text(session, packet)
    if not text:
        return RulesScan(RulesStatus.UNCLEAR, (), url, has_text=False)
    candidates = find_policy_sentences(text)
    return RulesScan(suggest_status(candidates), tuple(candidates), url, has_text=True)


def confirm_rules(  # pylint: disable=too-many-arguments
    session: Session,
    packet: Packet,
    status: RulesStatus,
    *,
    quote: str | None,
    scholarship_name: str,
    now: datetime | None = None,
) -> Packet:
    """FR-A2: the student confirms what the rules say."""
    if status is RulesStatus.UNCHECKED:
        raise RulesError("Choose allowed, prohibited or unclear.")
    text, url = _source_text(session, packet)
    clean_quote = " ".join((quote or "").split()) or None
    if status is RulesStatus.ALLOWED:
        if not clean_quote:
            raise RulesError(
                "To mark AI help as allowed, quote the sponsor's words that allow it."
            )
        if not text or not SourceText(text).contains_quote(clean_quote):
            raise RulesError(
                "That quote isn't on the scholarship's source page. AI help can "
                "only be allowed with the sponsor's own words as evidence."
            )
    now = now or datetime.now(UTC)
    packet.rules_status = status
    packet.rules_quote = clean_quote
    packet.rules_source_url = url
    packet.rules_confirmed_at = now
    session.add(
        AuditEvent(
            user_id=packet.user_id,
            scholarship_id=packet.scholarship_id,
            scholarship_name=scholarship_name,
            action=RULES_CONFIRMED,
            note=f"AI use: {status.value}",
            created_at=now,
        )
    )
    session.flush()
    return packet

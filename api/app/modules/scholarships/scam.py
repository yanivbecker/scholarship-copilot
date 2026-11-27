"""Warning signs that a "scholarship" may be a scam (FR-D9).

Deterministic pattern checks on the page text. Each flag keeps the line that
triggered it, so the student sees the evidence and decides. Flags are shown,
never used to hide a listing: a legitimate award can trip one by accident.

Based on common FTC guidance: real scholarships don't charge fees, don't
guarantee awards, and don't ask for bank or Social Security numbers to apply.

Known limit: these are word patterns, not understanding. Unusual phrasing can
slip through (e.g. "applications without a processing fee are rejected"), so
a listing with no flags isn't proof it's safe.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

MAX_EVIDENCE = 300


class ScamSignal(StrEnum):
    """Why a listing looks suspicious."""

    FEE = "fee"  # asks the applicant to pay
    GUARANTEED = "guaranteed"  # promises an award
    SENSITIVE_INFO = "sensitive_info"  # asks for SSN / bank / card details
    UNSOLICITED_WIN = "unsolicited_win"  # "you've been selected" / "you won"
    PRESSURE = "pressure"  # "act now", "only today"


SIGNAL_LABELS = {
    ScamSignal.FEE: "Asks for a fee",
    ScamSignal.GUARANTEED: "Promises a guaranteed award",
    ScamSignal.SENSITIVE_INFO: "Asks for bank, card or Social Security details",
    ScamSignal.UNSOLICITED_WIN: "Says you've already won or been selected",
    ScamSignal.PRESSURE: "Pressures you to act immediately",
}

_PATTERNS: dict[ScamSignal, re.Pattern[str]] = {
    ScamSignal.FEE: re.compile(
        r"\b(application|processing|registration|handling|redemption|"
        r"service|disbursement)\s+fees?\b"
        r"|\bpay\s+(a|the|an)?\s*\$\s?\d"
        r"|\bfee\s+of\s+\$\s?\d",
        re.IGNORECASE,
    ),
    ScamSignal.GUARANTEED: re.compile(
        r"\bguarantee(d|s)?\b[^.\n]{0,40}\b(scholarship|award|money|funding|win)"
        r"|\b(scholarship|award|money|funding)\b[^.\n]{0,40}\bguaranteed\b"
        r"|\bmoney[- ]back\s+guarantee\b",
        re.IGNORECASE,
    ),
    ScamSignal.SENSITIVE_INFO: re.compile(
        r"\b(social\s+security\s+(number|no\.?)|\bSSN\b|bank\s+account\s+"
        r"(number|details|information)|routing\s+number|credit\s+card\s+"
        r"(number|details|information)|debit\s+card\s+number)",
        re.IGNORECASE,
    ),
    ScamSignal.UNSOLICITED_WIN: re.compile(
        r"\byou\s+(have\s+been|'ve\s+been|were)\s+(selected|chosen)\b"
        r"|\b(congratulations|congrats)\b[^.\n]{0,40}\byou\b"
        r"[^.\n]{0,20}\b(won|win|selected)\b"
        r"|\byou\s+(have\s+)?won\b",
        re.IGNORECASE,
    ),
    ScamSignal.PRESSURE: re.compile(
        r"\b(act\s+now|only\s+today|today\s+only|limited\s+time\s+only|"
        r"respond\s+within\s+\d+\s+hours|before\s+it'?s\s+too\s+late)\b",
        re.IGNORECASE,
    ),
}


# "No application fee", "free to apply", "fees are waived": a good sign, not a bad one.
_NO_FEE = re.compile(
    r"\b(no|without|never|not|zero|free\s+of)\b[^.\n]{0,40}\bfees?\b"
    r"|\bfees?\b[^.\n]{0,20}\b(waived|not\s+required|not\s+charged)\b"
    r"|\bfree\s+to\s+apply\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScamFlag:
    """One warning sign and the line of text that triggered it."""

    signal: ScamSignal
    evidence: str

    @property
    def label(self) -> str:
        return SIGNAL_LABELS[self.signal]


def find_scam_flags(text: str) -> list[ScamFlag]:
    """At most one flag per signal, with the first line that triggered it."""
    flags: list[ScamFlag] = []
    lines = [" ".join(line.split()) for line in text.splitlines()]
    for signal, pattern in _PATTERNS.items():
        for line in lines:
            if signal is ScamSignal.FEE and _NO_FEE.search(line):
                continue
            if pattern.search(line):
                flags.append(ScamFlag(signal, line[:MAX_EVIDENCE]))
                break
    return flags

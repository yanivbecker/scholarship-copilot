"""Check that quoted evidence really appears in the source text (FR-D5).

An AI can paraphrase, merge sentences or invent text. A criterion is only
kept if its quote can be found in the page we actually fetched (or the text
the student pasted). Matching forgives differences that don't change meaning:
spacing and line breaks, letter case, and typographic variants of quotes,
dashes and spaces. Anything else must match exactly.
"""

import re
import unicodedata

MIN_QUOTE_CHARS = 12
MIN_QUOTE_WORDS = 3
MAX_QUOTE_CHARS = 1000

# Typographic look-alikes -> plain ASCII (by code point, so nothing in this
# file is an invisible character).
_SINGLE_QUOTES = (0x2018, 0x2019, 0x201A, 0x201B, 0x2032)
_DOUBLE_QUOTES = (0x201C, 0x201D, 0x201E, 0x2033)
_DASHES = (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212)
_SPACES = (0x00A0, 0x2009, 0x202F)
_INVISIBLE = (0x00AD, 0x200B)  # soft hyphen, zero-width space

_TRANSLATE: dict[int, str | None] = {
    **dict.fromkeys(_SINGLE_QUOTES, "'"),
    **dict.fromkeys(_DOUBLE_QUOTES, '"'),
    **dict.fromkeys(_DASHES, "-"),
    **dict.fromkeys(_SPACES, " "),
    **dict.fromkeys(_INVISIBLE, None),
}
_SPACE = re.compile(r"\s+")


def normalize_for_matching(text: str) -> str:
    """Lowercase, unify typographic characters, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    return _SPACE.sub(" ", text).strip().casefold()


class SourceText:
    """The page text, prepared once for many quote lookups."""

    def __init__(self, text: str) -> None:
        self._normalized = normalize_for_matching(text)

    def contains_quote(self, quote: str) -> bool:
        """True if `quote` is long enough to mean something and is in the text."""
        normalized = normalize_for_matching(quote)
        if len(normalized) < MIN_QUOTE_CHARS or len(normalized) > MAX_QUOTE_CHARS:
            return False
        if len(normalized.split()) < MIN_QUOTE_WORDS:
            return False
        return normalized in self._normalized

    def contains_phrase(self, phrase: str) -> bool:
        """For short exact phrases such as an amount ("$2,000"): no length rule."""
        normalized = normalize_for_matching(phrase)
        return len(normalized) >= 2 and normalized in self._normalized

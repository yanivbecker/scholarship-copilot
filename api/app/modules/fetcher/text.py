"""Readable text from fetched pages, and a hash to detect changes (FR-D7)."""

import hashlib
import io
import warnings

import lxml.html
from lxml.etree import ParserError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_TEXT_CHARS = 200_000
MAX_PDF_PAGES = 50

with warnings.catch_warnings():
    # trafilatura imports urllib3's optional SOCKS support; we never use it
    # (all requests go through our own fetcher).
    warnings.simplefilter("ignore")
    import trafilatura


class UnreadableContentError(ValueError):
    """The page couldn't be turned into text. The message is user-facing."""


def html_to_text(html: bytes) -> str:
    """Main text of an HTML page, without menus and footers where possible."""
    text = trafilatura.extract(
        html,
        include_tables=True,  # eligibility is often in a table
        include_links=False,
        favor_recall=True,  # better to keep a stray line than lose a criterion
    )
    if not text:
        # trafilatura skips very short pages; fall back to all visible text.
        text = _visible_text(html)
    if not text:
        raise UnreadableContentError("No readable text was found on the page.")
    return text[:MAX_TEXT_CHARS]


def _visible_text(html: bytes) -> str:
    """Every visible line of the page, without scripts, styles or menus."""
    try:
        root = lxml.html.fromstring(html)
    except (ParserError, ValueError):
        return ""
    for element in root.xpath("//script|//style|//noscript|//template|//nav"):
        element.drop_tree()
    lines = (" ".join(line.split()) for line in root.text_content().splitlines())
    return "\n".join(line for line in lines if line)


def pdf_to_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UnreadableContentError("The PDF is password-protected.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UnreadableContentError(f"The PDF has over {MAX_PDF_PAGES} pages.")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except UnreadableContentError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError):
        raise UnreadableContentError("The PDF couldn't be read.") from None
    if not text.strip():
        raise UnreadableContentError("No readable text was found in the PDF.")
    return text[:MAX_TEXT_CHARS]


def content_hash(text: str) -> str:
    """Same text (ignoring spacing differences) -> same hash."""
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

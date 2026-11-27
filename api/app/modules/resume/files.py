"""Check an uploaded resume and pull plain text out of it.

Uploaded files are untrusted input. So:
  * The type is decided by the file's first bytes, not its name or the
    Content-Type the browser sent (both are easy to fake).
  * Size, page count, text length and (for DOCX) unzipped size are capped, so a
    crafted file can't make the app hang or run out of memory ("zip bomb").
  * Parsing errors become a friendly message, never a crash.
"""

import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

import docx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB: plenty for a resume
MAX_PDF_PAGES = 20
MAX_TEXT_CHARS = 200_000
MAX_DOCX_UNZIPPED_BYTES = 30 * 1024 * 1024
MAX_FILENAME_LENGTH = 255

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"


class ResumeFileError(ValueError):
    """The file can't be used. The message is user-facing."""


@dataclass(frozen=True)
class ResumeFile:
    """A checked upload: what kind it is and the text inside."""

    kind: str  # "pdf" or "docx"
    content_type: str
    text: str


def clean_filename(name: str | None) -> str:
    """Keep only the last path part, for display. "C:\\x\\cv.pdf" -> "cv.pdf"."""
    base = PurePath((name or "").replace("\\", "/")).name.strip()
    return (base or "resume")[:MAX_FILENAME_LENGTH]


def read_resume(data: bytes) -> ResumeFile:
    """Identify the file by its content and extract its text."""
    if not data:
        raise ResumeFileError("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ResumeFileError("The file is larger than 5 MB.")
    if data.startswith(PDF_MAGIC):
        return ResumeFile("pdf", "application/pdf", _pdf_text(data))
    if data.startswith(ZIP_MAGIC):
        return ResumeFile(
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            _docx_text(data),
        )
    raise ResumeFileError("Upload a PDF or Word (.docx) file.")


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ResumeFileError(
                "This PDF is password-protected. Save an unprotected copy and "
                "try again."
            )
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ResumeFileError(f"The PDF has more than {MAX_PDF_PAGES} pages.")
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
            total += len(text)
            if total > MAX_TEXT_CHARS:
                break
    except ResumeFileError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError):
        raise ResumeFileError("This PDF couldn't be read. It may be damaged.") from None
    return _finish("\n".join(parts))


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            unzipped = sum(info.file_size for info in archive.infolist())
        if "word/document.xml" not in names:
            raise ResumeFileError("Upload a PDF or Word (.docx) file.")
        if unzipped > MAX_DOCX_UNZIPPED_BYTES:
            raise ResumeFileError("This Word file is too large once unpacked.")
        document = docx.Document(io.BytesIO(data))
    except ResumeFileError:
        raise
    except (zipfile.BadZipFile, ValueError, KeyError, OSError):
        raise ResumeFileError(
            "This Word file couldn't be read. It may be damaged."
        ) from None
    lines = [p.text for p in document.paragraphs]
    for table in document.tables:  # many resume templates use tables
        for row in table.rows:
            lines.append("  ".join(cell.text for cell in row.cells))
    return _finish("\n".join(lines))


def _finish(text: str) -> str:
    text = text[:MAX_TEXT_CHARS].strip()
    if not text:
        raise ResumeFileError(
            "No text was found. If this is a scanned image, upload a version "
            "with selectable text."
        )
    return text

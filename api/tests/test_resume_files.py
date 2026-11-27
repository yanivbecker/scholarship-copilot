"""Resume upload checks: type by content, limits, damaged files."""

import pytest

from app.modules.resume.files import (
    MAX_PDF_PAGES,
    MAX_UPLOAD_BYTES,
    ResumeFileError,
    clean_filename,
    read_resume,
)
from tests.resume_files import (
    SAMPLE_LINES,
    make_blank_pdf,
    make_docx,
    make_pdf,
    make_zip,
)


def test_pdf_text_is_extracted() -> None:
    resume = read_resume(make_pdf(SAMPLE_LINES))

    assert resume.kind == "pdf"
    assert "GPA: 3.72/4.0" in resume.text


def test_docx_text_includes_tables() -> None:
    resume = read_resume(make_docx(["Test Person"], [["GPA: 3.9/4.0", "2025"]]))

    assert resume.kind == "docx"
    assert "Test Person" in resume.text and "GPA: 3.9/4.0" in resume.text


def test_type_comes_from_content_not_name() -> None:
    # A text file renamed to .pdf is still a text file.
    with pytest.raises(ResumeFileError, match="PDF or Word"):
        read_resume(b"just some text pretending to be a pdf")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"%PDF-" + b"0" * MAX_UPLOAD_BYTES, "5 MB"),
        (b"%PDF-1.4 this is not really a pdf", "couldn't be read"),
        (make_blank_pdf(password="secret"), "password-protected"),
        (make_blank_pdf(pages=MAX_PDF_PAGES + 1), "more than"),
        (make_blank_pdf(), "No text was found"),  # e.g. a scanned image
        (make_zip({"hello.txt": b"hi"}), "PDF or Word"),  # a zip, not a docx
        (b"PK\x03\x04 broken zip", "couldn't be read"),
    ],
)
def test_unusable_files_get_a_clear_message(data: bytes, message: str) -> None:
    with pytest.raises(ResumeFileError, match=message):
        read_resume(data)


def test_zip_bomb_is_refused_before_parsing() -> None:
    # 40 MB of zeros compresses to a few KB; we refuse based on unpacked size.
    bomb = make_zip({"word/document.xml": b"0" * (40 * 1024 * 1024)})

    assert len(bomb) < 1024 * 1024
    with pytest.raises(ResumeFileError, match="too large once unpacked"):
        read_resume(bomb)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cv.pdf", "cv.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\My Resume.docx", "My Resume.docx"),
        ("", "resume"),
        (None, "resume"),
        ("x" * 300 + ".pdf", "x" * 255),
    ],
)
def test_clean_filename(raw: str | None, expected: str) -> None:
    assert clean_filename(raw) == expected

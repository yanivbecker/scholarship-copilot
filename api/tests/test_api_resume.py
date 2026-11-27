"""Resume upload + confirm API (FR-P2). All files are fictional test data."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.storage import LocalFileStorage
from app.modules.documents.models import Document
from tests.resume_files import SAMPLE_LINES, make_docx, make_pdf

URL = "/api/v1/resume"


def upload(client: TestClient, data: bytes, name: str = "cv.pdf") -> dict[str, Any]:
    response = client.post(URL, files={"file": (name, data, "application/pdf")})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_upload_returns_suggestions_but_saves_no_facts(client: TestClient) -> None:
    client.put("/api/v1/facts/gpa", json={"value": 3.5})

    body = upload(client, make_pdf(SAMPLE_LINES), "Jordan Resume.pdf")

    assert body["filename"] == "Jordan Resume.pdf"
    by_key = {s["key"]: s for s in body["suggestions"]}
    assert by_key["gpa"]["value"] == 3.72
    assert by_key["gpa"]["label"] == "GPA"
    assert by_key["gpa"]["evidence"] == "GPA: 3.72/4.0"
    assert by_key["gpa"]["current_value"] == 3.5  # so the UI can say "replaces"
    assert [f["key"] for f in client.get("/api/v1/facts").json()] == ["gpa"]


def test_unchanged_value_is_saved_with_resume_origin(client: TestClient) -> None:
    doc = upload(client, make_pdf(SAMPLE_LINES))

    response = client.post(
        f"{URL}/{doc['document_id']}/confirm", json={"facts": {"gpa": 3.72}}
    )

    assert response.status_code == 200
    [fact] = response.json()
    assert fact["origin"] == "resume" and fact["origin_detail"] == "cv.pdf"


def test_edited_value_is_honestly_marked_manual(client: TestClient) -> None:
    doc = upload(client, make_pdf(SAMPLE_LINES))

    [fact] = client.post(
        f"{URL}/{doc['document_id']}/confirm", json={"facts": {"gpa": 3.8}}
    ).json()

    assert fact["value"] == 3.8
    assert fact["origin"] == "manual"
    assert fact["origin_detail"] == "edited from cv.pdf"


def test_facts_not_in_the_resume_cannot_be_claimed(client: TestClient) -> None:
    doc = upload(client, make_pdf(SAMPLE_LINES))

    response = client.post(
        f"{URL}/{doc['document_id']}/confirm",
        json={"facts": {"gpa": 3.72, "household_income": 50000}},
    )

    assert response.status_code == 422
    assert set(response.json()["field_errors"]) == {"household_income"}
    assert client.get("/api/v1/facts").json() == []  # all or nothing


def test_invalid_edit_reports_the_field(client: TestClient) -> None:
    doc = upload(client, make_pdf(SAMPLE_LINES))

    response = client.post(
        f"{URL}/{doc['document_id']}/confirm", json={"facts": {"gpa": 9.0}}
    )

    assert response.status_code == 422
    assert "gpa" in response.json()["field_errors"]


def test_docx_upload_works(client: TestClient) -> None:
    body = upload(client, make_docx(SAMPLE_LINES), "cv.docx")

    assert {"gpa", "school_name"} <= {s["key"] for s in body["suggestions"]}


def test_rejected_upload_stores_nothing(
    client: TestClient, session: Session, storage: LocalFileStorage
) -> None:
    response = client.post(
        URL, files={"file": ("cv.pdf", b"not a pdf at all", "application/pdf")}
    )

    assert response.status_code == 422
    assert "PDF or Word" in response.json()["detail"]
    assert session.scalar(select(func.count()).select_from(Document)) == 0
    assert not storage.root.exists() or not any(storage.root.iterdir())


def test_file_is_stored_outside_the_repo_under_a_random_name(
    client: TestClient, session: Session, storage: LocalFileStorage
) -> None:
    upload(client, make_pdf(SAMPLE_LINES), "../../evil.pdf")

    document = session.scalars(select(Document)).one()
    assert document.original_filename == "evil.pdf"
    assert "evil" not in document.storage_key
    assert (storage.root / document.storage_key).exists()


def test_delete_removes_the_file_but_keeps_confirmed_facts(
    client: TestClient, storage: LocalFileStorage
) -> None:
    doc = upload(client, make_pdf(SAMPLE_LINES))
    client.post(f"{URL}/{doc['document_id']}/confirm", json={"facts": {"gpa": 3.72}})

    assert client.delete(f"{URL}/{doc['document_id']}").status_code == 204

    assert not list(storage.root.glob("*"))
    assert [f["key"] for f in client.get("/api/v1/facts").json()] == ["gpa"]
    assert client.delete(f"{URL}/{doc['document_id']}").status_code == 404


def test_unknown_document_is_404(client: TestClient) -> None:
    response = client.post(f"{URL}/999/confirm", json={"facts": {}})

    assert response.status_code == 404

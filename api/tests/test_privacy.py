"""Delete all personal data (NFR-12). All data here is fictional."""

import io
from pathlib import Path

from sqlalchemy.orm import Session

from app.cli import CONFIRM_WORD, run
from app.core.storage import LocalFileStorage
from app.modules.privacy.service import count_personal_data, delete_all_personal_data
from app.modules.profile import service as profile
from app.modules.profile.models import FactOrigin
from app.modules.resume.service import upload_resume
from app.modules.sources.service import add_source
from app.modules.users.models import User
from app.modules.users.service import get_or_create_owner
from tests.resume_files import SAMPLE_LINES, make_pdf


def fill_with_data(session: Session, storage: LocalFileStorage) -> None:
    owner = get_or_create_owner(session)
    profile.get_or_create_profile(session, owner.id)
    profile.set_fact(session, owner.id, "gpa", 3.5, origin=FactOrigin.MANUAL)
    profile.create_story(session, owner.id, title="T", body="b", themes=["x"])
    add_source(session, owner.id, url="https://example.org/awards")
    upload_resume(
        session, storage, owner.id, filename="cv.pdf", data=make_pdf(SAMPLE_LINES)
    )
    session.commit()
    storage.save(b"orphan", suffix=".pdf")  # a file no row points to


def test_dry_run_counts_but_deletes_nothing(
    session: Session, storage: LocalFileStorage
) -> None:
    fill_with_data(session, storage)

    report = delete_all_personal_data(session, storage, dry_run=True)

    assert report.rows_by_table == {
        "users": 1,
        "profiles": 1,
        "profile_facts": 1,
        "stories": 1,
        "sources": 1,
        "documents": 1,
    }
    assert report.files == 2
    assert count_personal_data(session, storage).total_rows == 6


def test_everything_is_deleted_including_stray_files(
    session: Session, storage: LocalFileStorage
) -> None:
    fill_with_data(session, storage)

    delete_all_personal_data(session, storage)

    after = count_personal_data(session, storage)
    assert after.total_rows == 0
    assert after.files == 0


def test_deleted_text_is_gone_from_the_database_file(
    session: Session, storage: LocalFileStorage, db_url: str
) -> None:
    # SQLite normally leaves deleted rows in the file until the space is
    # reused, so private text could still be read with a hex editor.
    # VACUUM rewrites the file without them.
    fill_with_data(session, storage)
    owner = get_or_create_owner(session)
    marker = "PRIVATE-MARKER-7f3a"
    for i in range(50):  # enough rows to span many database pages
        profile.create_story(
            session, owner.id, title=f"S{i}", body=f"{marker} " * 100, themes=[]
        )
    session.commit()
    db_file = Path(db_url.removeprefix("sqlite:///"))
    assert marker.encode() in db_file.read_bytes()

    delete_all_personal_data(session, storage)
    session.close()

    assert marker.encode() not in db_file.read_bytes()


def test_app_still_works_afterwards(
    session: Session, storage: LocalFileStorage
) -> None:
    fill_with_data(session, storage)
    delete_all_personal_data(session, storage)

    get_or_create_owner(session)  # schema intact: a fresh start works
    session.commit()
    assert session.query(User).count() == 1


# --- CLI ---------------------------------------------------------------------


def cli(
    session: Session, storage: LocalFileStorage, *args: str, answer: str = ""
) -> tuple[int, str]:
    out = io.StringIO()
    code = run(
        ["delete-my-data", *args],
        session_factory=lambda: Session(session.get_bind()),
        storage=storage,
        ask=lambda _prompt: answer,
        out=out,
    )
    return code, out.getvalue()


def test_cli_asks_and_cancels_unless_the_word_is_typed(
    session: Session, storage: LocalFileStorage
) -> None:
    fill_with_data(session, storage)

    code, output = cli(session, storage, answer="yes")

    assert code == 1
    assert "Cancelled. Nothing was deleted." in output
    assert count_personal_data(session, storage).total_rows == 6


def test_cli_deletes_after_confirmation(
    session: Session, storage: LocalFileStorage
) -> None:
    fill_with_data(session, storage)

    code, output = cli(session, storage, answer=CONFIRM_WORD)

    assert code == 0
    assert "Deleted:" in output and "rows in profile_facts" in output
    assert "sqlite:///" in output  # shows which database it was
    assert count_personal_data(session, storage).total_rows == 0


def test_cli_dry_run_and_yes(session: Session, storage: LocalFileStorage) -> None:
    fill_with_data(session, storage)

    _, dry = cli(session, storage, "--dry-run")
    assert "Would delete:" in dry
    assert count_personal_data(session, storage).total_rows == 6

    code, _ = cli(session, storage, "--yes")
    assert code == 0
    assert count_personal_data(session, storage).total_rows == 0

    _, empty = cli(session, storage, "--yes")
    assert "There is no personal data to delete." in empty

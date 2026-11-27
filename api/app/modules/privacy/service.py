"""Delete all personal data (NFR-12).

Removes every user and everything they own (rows cascade through user_id),
every stored file, and on SQLite compacts the database file so the deleted
rows don't linger in its free space. The schema (tables, migrations) stays,
so the app still starts afterwards, empty.
"""

from dataclasses import dataclass, field

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.storage import FileStorage
from app.models import Base
from app.modules.users.models import User


@dataclass
class DeletionReport:
    """What was (or, in a dry run, would be) deleted."""

    rows_by_table: dict[str, int] = field(default_factory=dict)
    files: int = 0
    dry_run: bool = False

    @property
    def total_rows(self) -> int:
        return sum(self.rows_by_table.values())


def count_personal_data(session: Session, storage: FileStorage) -> DeletionReport:
    """Count rows in every table that holds user data, plus stored files."""
    report = DeletionReport(files=len(storage.list_keys()))
    for table in Base.metadata.sorted_tables:
        if table.name == "users" or "user_id" in table.c:
            count = session.scalar(select(func.count()).select_from(table)) or 0
            if count:
                report.rows_by_table[table.name] = count
    return report


def delete_all_personal_data(
    session: Session, storage: FileStorage, *, dry_run: bool = False
) -> DeletionReport:
    """Delete everything personal. Commits. Returns what was deleted."""
    report = count_personal_data(session, storage)
    report.dry_run = dry_run
    if dry_run:
        return report

    # Rows first: if this fails, the files that rows point to still exist.
    for user in session.scalars(select(User)):
        session.delete(user)  # ON DELETE CASCADE removes everything they own
    session.commit()

    # Then every stored file, including any no record points to anymore.
    for key in storage.list_keys():
        storage.delete(key)

    engine = session.get_bind().engine
    if engine.dialect.name == "sqlite":
        # VACUUM can't run inside a transaction; use a fresh autocommit one.
        with engine.connect() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("VACUUM")
            )

    leftover = count_personal_data(session, storage)
    if leftover.total_rows or leftover.files:  # pragma: no cover - safety net
        raise RuntimeError(f"Deletion incomplete: {leftover}")
    return report

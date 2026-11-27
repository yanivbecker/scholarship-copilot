"""The `scholar` command-line tool. Run `uv run scholar --help` in api/.

Jobs (Phase 5+) and data deletion live here, so any scheduler or a person
at the terminal can run them (ARCHITECTURE.md: "jobs are CLI commands").
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from sqlalchemy.orm import Session

from app.core.db import get_session_factory
from app.core.storage import FileStorage, get_storage
from app.modules.privacy.service import DeletionReport, delete_all_personal_data

CONFIRM_WORD = "DELETE"


def _print_report(report: DeletionReport, out: TextIO) -> None:
    verb = "Would delete" if report.dry_run else "Deleted"
    if not report.total_rows and not report.files:
        print("There is no personal data to delete.", file=out)
        return
    print(f"{verb}:", file=out)
    for table, count in sorted(report.rows_by_table.items()):
        print(f"  {count:>6}  rows in {table}", file=out)
    print(f"  {report.files:>6}  stored files", file=out)


def cmd_delete_my_data(  # pylint: disable=too-many-arguments
    args: argparse.Namespace,
    *,
    session_factory: Callable[[], Session],
    storage: FileStorage,
    ask: Callable[[str], str],
    out: TextIO,
) -> int:
    with session_factory() as session:
        if args.dry_run:
            _print_report(delete_all_personal_data(session, storage, dry_run=True), out)
            return 0
        if not args.yes:
            print(
                "This permanently deletes your profile, facts, stories, sources,\n"
                "uploaded files and everything else the app stores about you.\n"
                # The database this session really uses (password hidden).
                "Database: "
                + session.get_bind().engine.url.render_as_string(hide_password=True),
                file=out,
            )
            answer = ask(f"Type {CONFIRM_WORD} to continue: ")
            if answer.strip() != CONFIRM_WORD:
                print("Cancelled. Nothing was deleted.", file=out)
                return 1
        _print_report(delete_all_personal_data(session, storage), out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scholar", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    delete = commands.add_parser(
        "delete-my-data",
        help="Delete all personal data (database rows and uploaded files).",
    )
    delete.add_argument(
        "--dry-run", action="store_true", help="Only show what would be deleted."
    )
    delete.add_argument(
        "--yes", action="store_true", help="Don't ask for confirmation."
    )
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    session_factory: Callable[[], Session] | None = None,
    storage: FileStorage | None = None,
    ask: Callable[[str], str] = input,
    out: TextIO = sys.stdout,
) -> int:
    """Entry point with every dependency injectable, so tests never touch
    the real database or data folder."""
    args = build_parser().parse_args(argv)
    if args.command == "delete-my-data":
        return cmd_delete_my_data(
            args,
            session_factory=session_factory or get_session_factory(),
            storage=storage or get_storage(),
            ask=ask,
            out=out,
        )
    raise AssertionError(f"Unhandled command {args.command}")  # pragma: no cover


def main() -> None:
    sys.exit(run())

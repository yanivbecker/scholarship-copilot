"""The `scholar` command-line tool. Run `uv run scholar --help` in api/.

Jobs (Phase 5+) and data deletion live here, so any scheduler or a person
at the terminal can run them (ARCHITECTURE.md: "jobs are CLI commands").
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.factory import build_ai_provider
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.storage import FileStorage, get_storage
from app.modules.fetcher.fetcher import PoliteFetcher
from app.modules.jobs.daily import SCHEDULE, run_daily
from app.modules.jobs.discovery import run_discovery
from app.modules.jobs.models import JobRun
from app.modules.privacy.service import DeletionReport, delete_all_personal_data
from app.modules.users.service import get_or_create_owner

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


def _print_run(job: JobRun, provider: AIProvider, out: TextIO) -> None:
    summary = job.summary
    for item in summary.get("sources", []):
        extra = f", extraction: {item['extraction']}" if item.get("extraction") else ""
        print(f"  {item['check']:<18} {item['url']}{extra}", file=out)
        if item.get("message"):
            print(f"  {'':<18} {item['message']}", file=out)
    print(
        f"Run {job.status}: {len(summary.get('sources', []))} sources checked, "
        f"{summary.get('scholarships_created', 0)} new and "
        f"{summary.get('scholarships_updated', 0)} updated scholarships"
        f" (AI provider: {provider.name}).",
        file=out,
    )


def cmd_discover(
    *,
    session_factory: Callable[[], Session],
    fetcher: PoliteFetcher,
    provider: AIProvider,
    out: TextIO,
) -> int:
    """Check every approved source and extract scholarships from changed pages."""
    with session_factory() as session:
        owner = get_or_create_owner(session)
        session.commit()
        job = run_discovery(
            session, user_id=owner.id, fetcher=fetcher, provider=provider, trigger="cli"
        )
        _print_run(job, provider, out)
        return 0 if job.status == "succeeded" else 1


def cmd_daily(  # pylint: disable=too-many-arguments
    *,
    scheduled: bool,
    session_factory: Callable[[], Session],
    fetcher: PoliteFetcher,
    provider: AIProvider,
    out: TextIO,
) -> int:
    """FR-N1: discovery, then notifications. Scheduled runs obey the switch."""
    with session_factory() as session:
        owner = get_or_create_owner(session)
        session.commit()
        result = run_daily(
            session,
            user_id=owner.id,
            fetcher=fetcher,
            provider=provider,
            trigger=SCHEDULE if scheduled else "cli",
        )
        if result.skipped:
            print(result.skipped, file=out)
            return 0
        if result.run is not None:
            _print_run(result.run, provider, out)
        else:
            print("Discovery failed; see the app's Today screen.", file=out)
        print(f"{result.notifications} new notification(s).", file=out)
        return 0 if result.ok else 1


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
    commands.add_parser(
        "discover",
        help="Check every approved source and extract scholarships from "
        "pages that changed.",
    )
    daily = commands.add_parser(
        "daily",
        help="The daily job: check sources, then create notifications.",
    )
    daily.add_argument(
        "--scheduled",
        action="store_true",
        help="Run as the background job: does nothing while background "
        "running is switched off (used by launchd).",
    )
    return parser


def run(  # pylint: disable=too-many-arguments  # every dependency is injectable
    argv: Sequence[str] | None = None,
    *,
    session_factory: Callable[[], Session] | None = None,
    storage: FileStorage | None = None,
    fetcher: PoliteFetcher | None = None,
    provider: AIProvider | None = None,
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
    if args.command == "discover":
        own_fetcher = fetcher is None
        fetcher = fetcher or PoliteFetcher()
        try:
            return cmd_discover(
                session_factory=session_factory or get_session_factory(),
                fetcher=fetcher,
                provider=provider or build_ai_provider(get_settings()),
                out=out,
            )
        finally:
            if own_fetcher:
                fetcher.close()
    if args.command == "daily":
        own_fetcher = fetcher is None
        fetcher = fetcher or PoliteFetcher()
        try:
            return cmd_daily(
                scheduled=args.scheduled,
                session_factory=session_factory or get_session_factory(),
                fetcher=fetcher,
                provider=provider or build_ai_provider(get_settings()),
                out=out,
            )
        finally:
            if own_fetcher:
                fetcher.close()
    raise AssertionError(f"Unhandled command {args.command}")  # pragma: no cover


def main() -> None:
    sys.exit(run())

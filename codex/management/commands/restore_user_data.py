"""``manage.py restore_user_data`` — read the sidecar, write the main DB."""

from __future__ import annotations

from pathlib import Path
from typing import override

from django.core.management.base import BaseCommand, CommandParser

from codex.settings import CONFIG_PATH
from codex.user_data.restore import restore, write_log


class Command(BaseCommand):
    """Restore user data from the sidecar SQLite file."""

    help = (
        "Read the user-data sidecar (default: "
        "$CODEX_CONFIG_DIR/user_data.sqlite) and write each row back "
        "into the main DB. Use after a main-DB rebuild."
    )

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--from",
            dest="from_path",
            type=Path,
            default=None,
            help="Path to an alternate sidecar file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Walk every row without writing — just log what would happen.",
        )
        parser.add_argument(
            "--log",
            dest="log_path",
            type=Path,
            default=None,
            help=(
                "Path to write the unmatched-rows log "
                "(default: $CODEX_CONFIG_DIR/restore_user_data.log)."
            ),
        )

    @override
    def handle(self, *_args, **options) -> None:
        sidecar_path: Path | None = options.get("from_path")
        dry_run: bool = bool(options.get("dry_run"))
        log_path: Path = options.get("log_path") or (
            CONFIG_PATH / "restore_user_data.log"
        )
        report = restore(sidecar_path=sidecar_path, dry_run=dry_run)
        write_log(report, log_path)
        self.stdout.write(self.style.SUCCESS(f"written: {report.written}"))
        if report.skipped:
            self.stdout.write(self.style.WARNING(f"skipped: {report.skipped}"))
        self.stdout.write(f"log: {log_path}")

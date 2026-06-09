"""Tests for snapshot_sidecar() → compressed dump → restore round-trips."""

from __future__ import annotations

import lzma
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from loguru import logger

from codex.user_data.dump import snapshot_sidecar
from codex.user_data.restore import restore
from codex.xz import date_stamp

if TYPE_CHECKING:
    from collections.abc import Iterator

_TMP_DIR: Final = Path("/tmp/codex.tests.sidecar.snapshot")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105


@contextmanager
def _capture_logs() -> Iterator[list[str]]:
    """Collect loguru INFO+ messages emitted inside the ``with`` block."""
    records: list[str] = []
    sink_id = logger.add(records.append, level="INFO", format="{message}")
    try:
        yield records
    finally:
        logger.remove(sink_id)


class SnapshotSidecarTests(TestCase):
    """The production snapshot path and restoring from its output."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        self.backup_dir = _TMP_DIR / "backups"  # pyright: ignore[reportUninitializedInstanceVariable]
        self.config_dir = _TMP_DIR / "config"  # pyright: ignore[reportUninitializedInstanceVariable]
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _patch_settings(self):
        # snapshot_sidecar / restore import these at call time.
        return patch.multiple(
            "codex.settings",
            BACKUP_DB_DIR=self.backup_dir,
            CONFIG_PATH=self.config_dir,
        )

    def test_snapshot_writes_dated_sql_xz_and_drops_legacy(self) -> None:
        User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        legacy = self.config_dir / "user_data.sqlite"
        legacy.write_bytes(b"stale binary sidecar")

        with self._patch_settings():
            counts = snapshot_sidecar()

        assert counts["users"] >= 1
        snapshot = self.backup_dir / f"user_data.{date_stamp()}.sql.xz"
        assert snapshot.is_file()
        # No uncompressed intermediate left behind.
        assert not snapshot.with_name(snapshot.name + ".tmp").exists()
        # The legacy binary sidecar is superseded and removed.
        assert not legacy.exists()

        # The compressed dump replays into a fresh DB with the user present.
        with lzma.open(snapshot, "rt", encoding="utf-8") as src:
            sql = src.read()
        mem = sqlite3.connect(":memory:")
        mem.executescript(sql)
        usernames = {row[0] for row in mem.execute("SELECT username FROM users")}
        assert "alice" in usernames

    def test_restore_default_reads_newest_snapshot(self) -> None:
        User.objects.create_user(username="bob", password=_TEST_PASSWORD)
        with self._patch_settings():
            snapshot_sidecar()
            User.objects.filter(username="bob").delete()
            assert not User.objects.filter(username="bob").exists()

            report = restore()

        assert report.written.get("users", 0) >= 1
        assert User.objects.filter(username="bob").exists()

    def test_restore_from_explicit_sql_xz(self) -> None:
        User.objects.create_user(username="carol", password=_TEST_PASSWORD)
        with self._patch_settings():
            snapshot_sidecar()
        snapshot = self.backup_dir / f"user_data.{date_stamp()}.sql.xz"
        User.objects.filter(username="carol").delete()

        report = restore(sidecar_path=snapshot)
        assert report.written.get("users", 0) >= 1
        assert User.objects.filter(username="carol").exists()

    def test_snapshot_logs_row_summary(self) -> None:
        """The shared snapshot path logs a summary for every caller."""
        User.objects.create_user(username="dave", password=_TEST_PASSWORD)
        with self._patch_settings(), _capture_logs() as logs:
            snapshot_sidecar()
        assert any("Snapshotted user data sidecar" in line for line in logs)

    def test_restore_logs_summary(self) -> None:
        """restore() logs a completion line so the admin restore leaves a trace."""
        User.objects.create_user(username="erin", password=_TEST_PASSWORD)
        with self._patch_settings():
            snapshot_sidecar()
            with _capture_logs() as logs:
                restore()
        assert any("Restored user data:" in line for line in logs)

    def test_dry_run_restore_logs_distinct_prefix(self) -> None:
        """A dry run logs its own prefix and never claims a real restore."""
        User.objects.create_user(username="frank", password=_TEST_PASSWORD)
        with self._patch_settings():
            snapshot_sidecar()
            with _capture_logs() as logs:
                restore(dry_run=True)
        assert any("Dry-run restore:" in line for line in logs)
        assert not any("Restored user data:" in line for line in logs)

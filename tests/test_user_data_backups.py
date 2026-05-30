"""Tests for sidecar backup naming, listing, and safe resolution."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final, override

from django.test import TestCase

from codex.user_data.backups import (
    list_sidecar_backups,
    newest_sidecar_backup,
    resolve_sidecar_backup,
)

_TMP_DIR: Final = Path("/tmp/codex.tests.sidecar.backups")  # noqa: S108


class SidecarBackupsTests(TestCase):
    """Listing + resolution of dated sidecar backups."""

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

    def _seed_dated(self) -> None:
        for name in (
            "user_data.2026-05-27.sql.xz",
            "user_data.2026-05-29.sql.xz",
            "user_data.2026-05-28.sql.xz",
            # Noise that must be ignored.
            "codex.sqlite3.2026-05-29.bak.xz",
            "user_data.sql.xz",
        ):
            (self.backup_dir / name).write_bytes(b"x")

    def test_list_is_newest_first_with_legacy_last(self) -> None:
        self._seed_dated()
        (self.config_dir / "user_data.sqlite").write_bytes(b"legacy")

        backups = list_sidecar_backups(self.backup_dir, self.config_dir)
        names = [b["name"] for b in backups]
        assert names == [
            "user_data.2026-05-29.sql.xz",
            "user_data.2026-05-28.sql.xz",
            "user_data.2026-05-27.sql.xz",
            "user_data.sqlite",
        ]
        assert backups[-1]["label"] == "legacy (uncompressed)"
        assert backups[0]["label"] == "2026-05-29"

    def test_newest_resolves_to_a_path(self) -> None:
        self._seed_dated()
        newest = newest_sidecar_backup(self.backup_dir, self.config_dir)
        assert newest == self.backup_dir / "user_data.2026-05-29.sql.xz"

    def test_newest_is_none_when_empty(self) -> None:
        assert newest_sidecar_backup(self.backup_dir, self.config_dir) is None

    def test_resolve_rejects_traversal_and_unknown(self) -> None:
        self._seed_dated()
        # Path traversal: only the basename is honored, which won't match.
        assert (
            resolve_sidecar_backup("../../etc/passwd", self.backup_dir, self.config_dir)
            is None
        )
        # A basename that doesn't match the strict pattern.
        assert (
            resolve_sidecar_backup("user_data.sql.xz", self.backup_dir, self.config_dir)
            is None
        )
        # A well-formed name that isn't on disk.
        assert (
            resolve_sidecar_backup(
                "user_data.1999-01-01.sql.xz", self.backup_dir, self.config_dir
            )
            is None
        )

    def test_resolve_accepts_valid_and_legacy(self) -> None:
        self._seed_dated()
        (self.config_dir / "user_data.sqlite").write_bytes(b"legacy")
        assert (
            resolve_sidecar_backup(
                "user_data.2026-05-28.sql.xz", self.backup_dir, self.config_dir
            )
            == self.backup_dir / "user_data.2026-05-28.sql.xz"
        )
        assert (
            resolve_sidecar_backup("user_data.sqlite", self.backup_dir, self.config_dir)
            == self.config_dir / "user_data.sqlite"
        )

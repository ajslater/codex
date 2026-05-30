"""Tests for the streamed, compressed, dated database backup."""

from __future__ import annotations

import lzma
import shutil
import sqlite3
from multiprocessing import Event
from pathlib import Path
from threading import Lock
from typing import Final, override
from unittest.mock import patch

from django.test import TestCase
from loguru import logger

from codex.compression import BACKUP_KEEP
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.janitor.janitor import Janitor

_TMP_DIR: Final = Path("/tmp/codex.tests.db.backup")  # noqa: S108
_VACUUM: Final = "codex.librarian.scribe.janitor.vacuum"


class DBBackupTests(TestCase):
    """Nightly + before-upgrade DB backups."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        _TMP_DIR.mkdir(parents=True, exist_ok=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _janitor() -> Janitor:
        return Janitor(logger, LIBRARIAN_QUEUE, Lock(), Event())

    def _patch_dirs(self):
        # Redirect every backup-dir reference at the vacuum module so the
        # real config/backups (and its legacy .bak) are never touched.
        return patch.multiple(
            _VACUUM,
            BACKUP_DB_DIR=_TMP_DIR,
            BACKUP_DB_PATH=_TMP_DIR / "codex.sqlite3.bak",
            _OLD_BACKUP_PATH=_TMP_DIR / "codex.sqlite3.bak.old",
        )

    def test_nightly_backup_is_compressed_dated_and_fts_intact(self) -> None:
        with self._patch_dirs():
            self._janitor().backup_db(show_status=False, prune=True)

        files = list(_TMP_DIR.glob("codex.sqlite3.*.bak.xz"))
        assert len(files) == 1

        restored = _TMP_DIR / "restored.sqlite3"
        with lzma.open(files[0], "rb") as src:
            restored.write_bytes(src.read())
        conn = sqlite3.connect(restored)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            # The FTS5 virtual table survives the serialize() round-trip — an
            # iterdump-based backup would lose it. A bare count proves the
            # table is registered and queryable.
            conn.execute("SELECT count(*) FROM codex_comicfts").fetchone()
        finally:
            conn.close()

    def test_prune_keeps_newest(self) -> None:
        for day in range(1, BACKUP_KEEP + 1):
            (_TMP_DIR / f"codex.sqlite3.2000-01-{day:02d}.bak.xz").write_bytes(b"x")
        with self._patch_dirs():
            # Writes today's (BACKUP_KEEP+1th) backup, then prunes back down.
            self._janitor().backup_db(show_status=False, prune=True)

        names = sorted(p.name for p in _TMP_DIR.glob("codex.sqlite3.*.bak.xz"))
        assert len(names) == BACKUP_KEEP
        assert "codex.sqlite3.2000-01-01.bak.xz" not in names

    def test_legacy_undated_backup_removed_on_prune(self) -> None:
        legacy = _TMP_DIR / "codex.sqlite3.bak"
        legacy.write_bytes(b"old")
        with self._patch_dirs():
            self._janitor().backup_db(show_status=False, prune=True)
        assert not legacy.exists()

    def test_before_upgrade_backup_compressed_not_pruned(self) -> None:
        # Seed a full dated set; the before-upgrade backup must not prune it.
        for day in range(1, BACKUP_KEEP + 1):
            (_TMP_DIR / f"codex.sqlite3.2000-01-{day:02d}.bak.xz").write_bytes(b"x")
        target = _TMP_DIR / "codex.sqlite3.before-v9.9.9.bak"
        with self._patch_dirs():
            self._janitor().backup_db(show_status=False, backup_path=target)

        assert (_TMP_DIR / "codex.sqlite3.before-v9.9.9.bak.xz").is_file()
        dated = list(_TMP_DIR.glob("codex.sqlite3.2000-*.bak.xz"))
        assert len(dated) == BACKUP_KEEP

"""
A move that loses its inode keeps the comic's read progress.

An inode is identity, so it pairs a move outright. Plenty of moves do not
keep one: a copy-then-delete, a cross-device ``mv``, a remount that
rotated the inode space. Those arrive as a delete plus an add, the delete
cascades ``Bookmark.comic`` away, and the add re-imports the same file as
a fresh, unread comic. The existence backstop cannot help, because the
old path really is gone.

The signature is the filename, size and mtime, so this covers a file that
moved and kept its name. A file renamed to a *different* name with a new
inode has nothing left to match on and is still a delete plus an add.

This drives the poller's own path — snapshot, diff, task, importer — so
the pairing is exercised where it actually runs.
"""

from __future__ import annotations

import shutil
from threading import Event, Lock
from typing import override

from django.contrib.auth.models import User
from loguru import logger

from codex.librarian.fs.import_task import build_import_task
from codex.librarian.fs.poller.snapshot import DatabaseSnapshot, DiskSnapshot
from codex.librarian.fs.poller.snapshot_diff import SnapshotDiff
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.models import Bookmark, Comic
from tests.importer.test_basic import LIBRARY_PATH
from tests.importer.test_delete_backstop import _DeleteTestBase

_ORIGINAL = LIBRARY_PATH / "Series" / "comic.cbz"
_MOVED = LIBRARY_PATH / "Series Two" / "comic.cbz"


class TestMovedBySignature(_DeleteTestBase):
    """A new-inode move is paired, not destroyed and re-created."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.subdir_folder = self._make_series_folder()

    def _make_series_folder(self):
        """Track the subdirectory the comic lives in."""
        from codex.models import Folder

        _ORIGINAL.parent.mkdir(parents=True, exist_ok=True)
        return Folder.objects.create(
            library=self.library,
            path=str(_ORIGINAL.parent),
            name=_ORIGINAL.parent.name,
        )

    def _poll(self) -> None:
        """Run the poller's diff and the importer phases a move needs."""
        db_snapshot = DatabaseSnapshot(self.library.path, logger)
        disk_snapshot = DiskSnapshot(self.library.path, logger)
        diff = SnapshotDiff(db_snapshot, disk_snapshot)
        task = build_import_task(self.library.pk, diff.to_events())
        if task is None:
            return
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        importer.move_and_modify_dirs()
        importer.delete()

    def test_new_inode_move_keeps_the_row_and_its_bookmark(self) -> None:
        """The reason this tier exists."""
        comic = self._create_comic(str(_ORIGINAL), folder=self.subdir_folder)
        user = User.objects.create_user(username="reader", password="x")  # noqa: S106
        bookmark = Bookmark.objects.create(user=user, comic=comic, finished=True)
        # copy2 preserves size and mtime; a fresh file gets a fresh inode,
        # which is exactly the shape inode pairing cannot see.
        _MOVED.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_ORIGINAL, _MOVED)
        _ORIGINAL.unlink()

        self._poll()

        comic.refresh_from_db()
        assert comic.path == str(_MOVED)
        assert Comic.objects.filter(pk=comic.pk).exists()
        assert Bookmark.objects.filter(pk=bookmark.pk, finished=True).exists()
        # Not re-imported as a second row.
        assert Comic.objects.filter(library=self.library).count() == 1

    def test_a_real_delete_is_still_a_delete(self) -> None:
        """Pairing must not resurrect a comic the user removed."""
        comic = self._create_comic(str(_ORIGINAL), folder=self.subdir_folder)
        _ORIGINAL.unlink()

        self._poll()

        assert not Comic.objects.filter(pk=comic.pk).exists()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_ORIGINAL.parent, ignore_errors=True)
        shutil.rmtree(_MOVED.parent, ignore_errors=True)
        super().tearDown()

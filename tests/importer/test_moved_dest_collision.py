"""
A move onto a claimed path must not crash the import.

The poller and watcher infer moves from inode matches without checking
that the destination is free in the database. A destination already held
by another row violated the ``(library, path)`` unique constraint inside
``bulk_update``, which aborted the whole import before the delete phase
could clear the stale row, so the same task crashed on every later scan.
Skipping the colliding move keeps the rest of the import running and lets
the next scan reconcile.
"""

import shutil
from pathlib import Path
from threading import Event, Lock
from typing import override
from unittest.mock import patch

from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from tests.importer.test_basic import (
    COMIC_PATH,
    LIBRARY_PATH,
    BaseTestImporter,
)

_SRC_PATH = str(LIBRARY_PATH / "src.cbz")
_DEST_PATH = str(LIBRARY_PATH / "dest.cbz")
_OTHER_PATH = str(LIBRARY_PATH / "other.cbz")
_FREE_PATH = str(LIBRARY_PATH / "free.cbz")


class TestImporterMoveDestCollision(BaseTestImporter):
    """Moves onto claimed destinations are skipped, not fatal."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.library = Library.objects.get(pk=self.task.library_id)
        self.folder = Folder.objects.create(
            library=self.library,
            path=str(LIBRARY_PATH),
            name=LIBRARY_PATH.name,
        )
        pub = Publisher.objects.create(name="Collision Pub")
        imp = Imprint.objects.create(name="Collision Imprint", publisher=pub)
        ser = Series.objects.create(name="Collision Series", imprint=imp, publisher=pub)
        self.tags = {
            "publisher": pub,
            "imprint": imp,
            "series": ser,
            "volume": Volume.objects.create(
                name="1", series=ser, imprint=imp, publisher=pub
            ),
        }
        self.issue_number = 0

    def _create_comic(self, path: str) -> Comic:
        """Create a comic with its file present, as presave stats disk."""
        shutil.copy(COMIC_PATH, path)
        self.issue_number += 1
        return Comic.objects.create(
            library=self.library,
            path=path,
            parent_folder=self.folder,
            issue_number=self.issue_number,
            name=Path(path).stem,
            size=1,
            page_count=1,
            **self.tags,
        )

    def _move(self, files_moved: dict[str, str]) -> ComicImporter:
        """Run the move phase with a fresh importer, as a scan would."""
        task = ImportTask(library_id=self.library.pk, files_moved=files_moved)
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        importer.move_and_modify_dirs()
        return importer

    def test_move_onto_tracked_dest_skipped(self) -> None:
        """A move onto a path another comic already holds is skipped."""
        src = self._create_comic(_SRC_PATH)
        dest = self._create_comic(_DEST_PATH)
        # The source file moved onto the destination on disk.
        Path(_SRC_PATH).unlink()

        importer = self._move({_SRC_PATH: _DEST_PATH})

        assert importer.counts.comics_moved == 0
        assert Comic.objects.get(pk=dest.pk).path == _DEST_PATH
        assert Comic.objects.get(pk=src.pk).path == _SRC_PATH

    def test_duplicate_destinations_keep_lowest_src(self) -> None:
        """Two sources claiming one destination keep only the first."""
        # "other" sorts before "src", so it wins the destination.
        other = self._create_comic(_OTHER_PATH)
        src = self._create_comic(_SRC_PATH)
        shutil.copy(COMIC_PATH, _FREE_PATH)
        Path(_OTHER_PATH).unlink()
        Path(_SRC_PATH).unlink()

        importer = self._move({_SRC_PATH: _FREE_PATH, _OTHER_PATH: _FREE_PATH})

        assert importer.counts.comics_moved == 1
        assert Comic.objects.get(pk=other.pk).path == _FREE_PATH
        assert Comic.objects.get(pk=src.pk).path == _SRC_PATH
        assert Comic.objects.filter(library=self.library, path=_FREE_PATH).count() == 1

    def test_chained_move_converges_over_two_scans(self) -> None:
        """A move onto a vacating path lands on the scan after it."""
        src = self._create_comic(_SRC_PATH)
        dest = self._create_comic(_DEST_PATH)
        # Both destination files are present, as they would be after a
        # chained rename on disk, so only the claimed path blocks a move.
        shutil.copy(COMIC_PATH, _FREE_PATH)
        Path(_SRC_PATH).unlink()

        # Scan one: the tail move is free, the head move is blocked.
        importer = self._move({_SRC_PATH: _DEST_PATH, _DEST_PATH: _FREE_PATH})

        assert importer.counts.comics_moved == 1
        assert Comic.objects.get(pk=dest.pk).path == _FREE_PATH
        assert Comic.objects.get(pk=src.pk).path == _SRC_PATH

        # Scan two: the destination is vacant now, so the head move lands.
        importer = self._move({_SRC_PATH: _DEST_PATH})

        assert importer.counts.comics_moved == 1
        assert Comic.objects.get(pk=src.pk).path == _DEST_PATH

    def test_move_phase_failure_does_not_abort(self) -> None:
        """Any move failure is contained so later phases still run."""
        src = self._create_comic(_SRC_PATH)
        shutil.copy(COMIC_PATH, _FREE_PATH)
        Path(_SRC_PATH).unlink()

        task = ImportTask(
            library_id=self.library.pk, files_moved={_SRC_PATH: _FREE_PATH}
        )
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        with patch.object(
            importer, "_bulk_comics_move_prepare", side_effect=RuntimeError("boom")
        ):
            importer.move_and_modify_dirs()

        assert importer.counts.comics_moved == 0
        assert Comic.objects.get(pk=src.pk).path == _SRC_PATH

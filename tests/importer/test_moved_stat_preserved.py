"""
A move must not refresh Comic.stat.

The stored stat means "the state of the file the last time its tags were
imported". Refreshing it during a move erases the only evidence the read
phase has that a renamed file's contents also changed, so a write-then-
rename would import its new tags never, rather than late.
"""

import shutil
from pathlib import Path
from threading import Event, Lock
from typing import override

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
    PATH,
    BaseTestImporter,
)

_NEW_PATH = str(LIBRARY_PATH / "renamed.cbz")
# Deliberately unlike anything on disk, per WatchedPath.set_stat's layout:
# [1] is the inode, [6] the size, [8] the mtime.
_SENTINEL_STAT = [1, 424242, 0, 0, 0, 0, 99, 0, 12345.0, 0]


class TestImporterMovePreservesStat(BaseTestImporter):
    """A moved comic keeps the stat from its last tag import."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # setUpTestData copies the fixture once per class, and this test
        # moves it away. Restore it so each method starts whole.
        shutil.copy(COMIC_PATH, PATH)
        library = Library.objects.get(pk=self.task.library_id)
        folder = Folder.objects.create(
            library=library, path=str(Path(PATH).parent), name=LIBRARY_PATH.name
        )
        pub = Publisher.objects.create(name="Move Test Pub")
        imp = Imprint.objects.create(name="Move Imprint", publisher=pub)
        ser = Series.objects.create(name="Move Series", imprint=imp, publisher=pub)
        vol = Volume.objects.create(name="1", series=ser, imprint=imp, publisher=pub)
        comic = Comic.objects.create(
            library=library,
            path=PATH,
            parent_folder=folder,
            issue_number=1,
            name="before",
            publisher=pub,
            imprint=imp,
            series=ser,
            volume=vol,
            size=1,
            page_count=1,
        )
        # Comic.save() presaves a real stat from disk, so plant the sentinel
        # with an update() that skips it.
        Comic.objects.filter(pk=comic.pk).update(stat=_SENTINEL_STAT)

    def test_move_preserves_stat(self) -> None:
        shutil.move(PATH, _NEW_PATH)
        task = ImportTask(
            library_id=self.task.library_id, files_moved={PATH: _NEW_PATH}
        )
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())

        importer.move_and_modify_dirs()

        comic = Comic.objects.get(path=_NEW_PATH)
        assert comic.parent_folder is not None
        assert comic.parent_folder.path == str(Path(_NEW_PATH).parent)
        assert comic.stat == _SENTINEL_STAT, comic.stat

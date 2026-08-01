"""
An external write-then-rename imports the new tags, not a failed import.

Every tagger that renames (including codex's own tag writer) writes tags
into the file and then renames it. Both land in one watch batch, so the
task carries a move plus a modify that still names the pre-rename path.
The importer applies the move first, and the modify used to be read from
the vanished old path: a phantom failed import, and tags that never
imported because the move had already refreshed Comic.stat to match disk.
"""

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock
from typing import override

from loguru import logger
from watchfiles import Change

from codex.librarian.fs.import_task import build_import_task
from codex.librarian.fs.watcher.events import process_changes
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.models import Comic, FailedImport
from tests.importer.test_basic import (
    COMIC_PATH,
    LIBRARY_PATH,
    PATH,
    BaseTestImporter,
    run_full_import,
)

_NEW_PATH = str(LIBRARY_PATH / "Captain Science v1950 #001.cbz")
# Predates the fixture archive's embedded metadata mtime, so comicbox
# re-parses the tags instead of short-circuiting on them.
_STALE_METADATA_MTIME = datetime(2020, 1, 1, tzinfo=UTC)


class TestImporterWriteThenRename(BaseTestImporter):
    """A moved comic whose contents also changed re-reads its tags."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # setUpTestData copies the fixture once per class, and this test
        # renames it away. Restore it so each method starts whole.
        shutil.copy(COMIC_PATH, PATH)
        run_full_import(self.importer)
        # Stand in for the tag write: the archive's bytes changed, so its
        # filesystem mtime advances past the stat stored at import.
        mtime = Path(PATH).stat().st_mtime + 100
        os.utime(PATH, (mtime, mtime))
        Comic.objects.filter(path=PATH).update(
            name="stale", metadata_mtime=_STALE_METADATA_MTIME
        )
        # Then the rename.
        shutil.move(PATH, _NEW_PATH)

    def test_write_then_rename_reimports_tags(self) -> None:
        # Drive the real watcher pipeline from the raw changes the kernel
        # coalesces into one batch: the tag write's modify on the old path,
        # and the rename's delete+add that inode matching pairs into a move.
        changes = {
            (Change.modified, PATH),
            (Change.deleted, PATH),
            (Change.added, _NEW_PATH),
        }
        events = [
            event
            for library_pk, event in process_changes(
                changes, {str(LIBRARY_PATH): self.task.library_id}
            )
            if library_pk == self.task.library_id
        ]
        task = build_import_task(self.task.library_id, events)
        assert task
        assert task.files_moved == {PATH: _NEW_PATH}
        assert task.files_modified == {_NEW_PATH}
        importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())

        importer.move_and_modify_dirs()
        run_full_import(importer)

        assert not FailedImport.objects.exists(), list(
            FailedImport.objects.values_list("path", "name")
        )
        comic = Comic.objects.get(path=_NEW_PATH)
        assert comic.name == "The Beginning", comic.name

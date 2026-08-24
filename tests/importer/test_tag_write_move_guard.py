"""
A scan that lands mid tag-write must not reconcile the paths it is moving.

Writing tags to a CBR converts it to a CBZ at a new inode, so neither the
watcher nor the poller can pair the change into a move. A watcher batch
force-yielded during a long write (or a poll landing in it) therefore
carries the conversion as an unrelated delete plus create, and it reaches
the importer *before* the tag writer's end-of-batch move task. Deleting
the row by its now-dead path would cascade the comic's bookmarks away and
leave the move with no source. ``_defer_pending_tag_write_moves`` holds
those paths for the task that owns them.
"""

import shutil
from pathlib import Path
from threading import Event, Lock
from typing import override

from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.tagwrite_moves import (
    clear_tag_write_moves,
    get_pending_tag_write_paths,
    register_tag_write_move,
)
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

# The DB path, the interim archive the conversion wrote, and the final
# name the rename pass gave it.
_CBR_PATH = str(LIBRARY_PATH / "converted.cbr")
_CBZ_PATH = str(LIBRARY_PATH / "converted.cbz")
_RENAMED_PATH = str(LIBRARY_PATH / "Renamed #001.cbz")
_UNRELATED_PATH = str(LIBRARY_PATH / "unrelated.cbz")
_UNRELATED_PATH_ALT = str(LIBRARY_PATH / "unrelated-alt.cbz")


class TestImporterTagWriteMoveGuard(BaseTestImporter):
    """Paths an in-flight tag write owns are deferred to its own task."""

    @override
    def setUp(self) -> None:
        super().setUp()
        clear_tag_write_moves()
        self.library = Library.objects.get(pk=self.task.library_id)
        self.folder = Folder.objects.create(
            library=self.library,
            path=str(LIBRARY_PATH),
            name=LIBRARY_PATH.name,
        )
        pub = Publisher.objects.create(name="Guard Pub")
        imp = Imprint.objects.create(name="Guard Imprint", publisher=pub)
        ser = Series.objects.create(name="Guard Series", imprint=imp, publisher=pub)
        self.tags = {
            "publisher": pub,
            "imprint": imp,
            "series": ser,
            "volume": Volume.objects.create(
                name="1", series=ser, imprint=imp, publisher=pub
            ),
        }
        self.issue_number = 0

    @override
    def tearDown(self) -> None:
        clear_tag_write_moves()
        super().tearDown()

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

    def _importer(self, **task_kwargs) -> ComicImporter:
        task = ImportTask(library_id=self.library.pk, **task_kwargs)
        return ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())

    @staticmethod
    def _register_conversion() -> None:
        """Register the move a tag write is about to enqueue."""
        register_tag_write_move(_CBR_PATH, _RENAMED_PATH, (_CBZ_PATH,))

    def test_delete_of_a_pending_move_source_is_deferred(self) -> None:
        """The row the pending move needs survives the scan's delete."""
        comic = self._create_comic(_CBR_PATH)
        self._register_conversion()
        importer = self._importer(files_deleted=frozenset({_CBR_PATH}))

        importer._defer_pending_tag_write_moves()  # noqa: SLF001
        importer.delete()

        assert not importer.task.files_deleted
        assert importer.counts.comics_deleted == 0
        assert Comic.objects.filter(pk=comic.pk).exists()

    def test_create_of_a_pending_move_path_is_deferred(self) -> None:
        """The interim and final archives are not imported as new comics."""
        self._create_comic(_CBR_PATH)
        self._register_conversion()
        importer = self._importer(
            files_created=frozenset({_CBZ_PATH, _RENAMED_PATH}),
        )

        importer._defer_pending_tag_write_moves()  # noqa: SLF001

        assert not importer.task.files_created

    def test_unregistered_paths_are_untouched(self) -> None:
        """A guard for one comic never defers another comic's delete."""
        comic = self._create_comic(_UNRELATED_PATH)
        self._register_conversion()
        importer = self._importer(files_deleted=frozenset({_UNRELATED_PATH}))

        importer._defer_pending_tag_write_moves()  # noqa: SLF001
        importer.delete()

        assert importer.counts.comics_deleted == 1
        assert not Comic.objects.filter(pk=comic.pk).exists()

    def test_carrying_the_move_releases_its_own_guard(self) -> None:
        """The tag writer's own task keeps the move and the re-read it asked for."""
        self._create_comic(_CBR_PATH)
        self._register_conversion()
        importer = self._importer(
            files_moved={_CBR_PATH: _RENAMED_PATH},
            files_modified=frozenset({_RENAMED_PATH}),
        )

        importer._defer_pending_tag_write_moves()  # noqa: SLF001

        # Its own move and re-read survive...
        assert importer.task.files_moved == {_CBR_PATH: _RENAMED_PATH}
        assert importer.task.files_modified == frozenset({_RENAMED_PATH})
        # ...and the guard is gone, so a later scan reconciles normally.
        later = self._importer(files_deleted=frozenset({_CBZ_PATH}))
        later._defer_pending_tag_write_moves()  # noqa: SLF001
        assert later.task.files_deleted == frozenset({_CBZ_PATH})

    def test_a_different_destination_does_not_release_the_guard(self) -> None:
        """Only the registered move reconciles it; a scanner's guess must not."""
        comic = self._create_comic(_CBR_PATH)
        self._register_conversion()
        # A scanner inferred some other destination for the same source.
        scan = self._importer(
            files_moved={_CBR_PATH: _UNRELATED_PATH},
            files_deleted=frozenset({_CBZ_PATH}),
        )

        scan._defer_pending_tag_write_moves()  # noqa: SLF001

        # The guard held, so the interim archive was not reaped...
        assert not scan.task.files_deleted
        # ...and the real move still finds its source row.
        move = self._importer(files_moved={_CBR_PATH: _RENAMED_PATH})
        move._defer_pending_tag_write_moves()  # noqa: SLF001
        assert not get_pending_tag_write_paths()
        assert Comic.objects.filter(pk=comic.pk).exists()

    def test_a_tasks_own_move_paths_are_never_deferred(self) -> None:
        """A task's own move survives even when its guard is still registered."""
        self._create_comic(_CBR_PATH)
        # Registered against a different destination, so the release
        # below does not fire and the guard stays live.
        register_tag_write_move(_CBR_PATH, _UNRELATED_PATH, (_CBZ_PATH,))
        importer = self._importer(
            files_moved={_CBR_PATH: _UNRELATED_PATH_ALT},
            files_modified=frozenset({_UNRELATED_PATH_ALT}),
        )

        importer._defer_pending_tag_write_moves()  # noqa: SLF001

        assert importer.task.files_moved == {_CBR_PATH: _UNRELATED_PATH_ALT}
        assert importer.task.files_modified == frozenset({_UNRELATED_PATH_ALT})

    def test_scan_delete_then_move_keeps_the_original_row(self) -> None:
        """End to end: the scan is a no-op and the move lands on the same row."""
        comic = self._create_comic(_CBR_PATH)
        # The conversion happened on disk: the cbr is gone, the renamed
        # cbz is in its place.
        shutil.copy(COMIC_PATH, _RENAMED_PATH)
        Path(_CBR_PATH).unlink()
        self._register_conversion()

        # The scan that force-flushed mid-write runs first.
        scan = self._importer(
            files_deleted=frozenset({_CBR_PATH}),
            files_created=frozenset({_CBZ_PATH}),
        )
        scan._defer_pending_tag_write_moves()  # noqa: SLF001
        scan.delete()

        # Then the tag writer's move task.
        move = self._importer(files_moved={_CBR_PATH: _RENAMED_PATH})
        move._defer_pending_tag_write_moves()  # noqa: SLF001
        move.move_and_modify_dirs()

        assert move.counts.comics_moved == 1
        comic.refresh_from_db()
        assert comic.path == _RENAMED_PATH

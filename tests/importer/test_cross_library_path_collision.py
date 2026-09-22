"""
Nested library roots must not resolve each other's rows.

``WatchedPath`` is unique on ``(library, path)``, not on ``path``, so a
library at ``/media`` and another at ``/media/comics`` legitimately hold
the same absolute path twice. Every bare ``path=``/``path__in=`` lookup
in the importer therefore picked an arbitrary library's row: the outer
library's comics were relinked and its bookmarks destroyed as a side
effect of scanning the inner one, and ``_get_parent_folder``'s
``Folder.objects.get(path=...)`` raised an uncaught
``MultipleObjectsReturned`` outright.
"""

import shutil
from threading import Event, Lock
from typing import override

from django.contrib.auth.models import User
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.statii.create import ImporterCreateTagsStatus
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import (
    Bookmark,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from tests.importer.test_basic import COMIC_PATH, TMP_DIR, BaseTestImporter

# A second library root nested inside the one BaseTestImporter creates.
_INNER_DIR = TMP_DIR / "inner"
_INNER_PATH = str(_INNER_DIR / "test.cbz")
_BOOKMARK_PAGE = 42
_EXPECTED_ROWS_PER_PATH = 2


class TestCrossLibraryPathCollision(BaseTestImporter):
    """Importing the inner library leaves the outer library's rows alone."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # BaseTestImporter's library covers TMP_DIR, so it is the outer one.
        self.outer_library = Library.objects.get(pk=self.task.library_id)
        _INNER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(COMIC_PATH, _INNER_PATH)
        self.inner_library = Library.objects.create(path=str(_INNER_DIR))
        self._seed_outer_library()
        # Now scan the inner library over the same files.
        self.task = ImportTask(
            library_id=self.inner_library.pk, files_modified=frozenset({_INNER_PATH})
        )
        self.importer = ComicImporter(
            self.task, logger, LIBRARIAN_QUEUE, Lock(), Event()
        )

    def _seed_outer_library(self) -> None:
        """Track the nested tree in the outer library, as its own scan would."""
        self.outer_folder = Folder.objects.create(
            library=self.outer_library, path=str(_INNER_DIR), name=_INNER_DIR.name
        )
        publisher = Publisher.objects.create(name="Outer Pub")
        imprint = Imprint.objects.create(name="Outer Imprint", publisher=publisher)
        series = Series.objects.create(
            name="Outer Series", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="1", series=series, imprint=imprint, publisher=publisher
        )
        self.outer_comic = Comic.objects.create(
            library=self.outer_library,
            path=_INNER_PATH,
            parent_folder=self.outer_folder,
            issue_number=1,
            name="outer",
            size=1,
            page_count=1,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
        )
        self.outer_comic.folders.add(self.outer_folder)
        user = User.objects.create_user(username="collision", password="pw-S106-x")  # noqa: S106
        self.outer_bookmark = Bookmark.objects.create(
            user=user, comic=self.outer_comic, page=_BOOKMARK_PAGE
        )

    def _import(self) -> None:
        """Run the per-comic phases the way a real scan chunk does."""
        self.importer.read()
        self.importer.query()
        self.importer.create_and_update()
        self.importer.link()

    def test_import_creates_its_own_rows(self) -> None:
        """The inner library gets its own Comic and Folder at the shared path."""
        self._import()

        assert Comic.objects.filter(path=_INNER_PATH).count() == _EXPECTED_ROWS_PER_PATH
        assert (
            Folder.objects.filter(path=str(_INNER_DIR)).count()
            == _EXPECTED_ROWS_PER_PATH
        )
        comic = Comic.objects.get(library=self.inner_library, path=_INNER_PATH)
        assert comic.pk != self.outer_comic.pk

    def test_import_leaves_the_outer_library_intact(self) -> None:
        """The outer library keeps its comic, its links and its bookmarks."""
        self._import()

        outer = Comic.objects.get(pk=self.outer_comic.pk)
        assert outer.library == self.outer_library
        assert outer.name == "outer"
        assert outer.parent_folder == self.outer_folder
        assert set(outer.folders.values_list("pk", flat=True)) == {self.outer_folder.pk}
        bookmark = Bookmark.objects.get(pk=self.outer_bookmark.pk)
        assert bookmark.page == _BOOKMARK_PAGE

    def test_imported_comic_links_its_own_folder(self) -> None:
        """Folder links resolve inside the importing library, not the outer one."""
        self._import()

        comic = Comic.objects.get(library=self.inner_library, path=_INNER_PATH)
        inner_folder = Folder.objects.get(
            library=self.inner_library, path=str(_INNER_DIR)
        )
        assert comic.parent_folder == inner_folder
        folder_pks = set(comic.folders.values_list("pk", flat=True))
        assert inner_folder.pk in folder_pks
        assert self.outer_folder.pk not in folder_pks

    def test_parent_folder_lookup_survives_a_duplicate_path(self) -> None:
        """``bulk_folders_create`` no longer raises MultipleObjectsReturned."""
        subdir = _INNER_DIR / "Nested"
        subdir.mkdir(exist_ok=True)
        # Both libraries track the parent, which is what made the old
        # ``Folder.objects.get(path=...)`` ambiguous.
        inner_folder = Folder.objects.create(
            library=self.inner_library, path=str(_INNER_DIR), name=_INNER_DIR.name
        )
        status = ImporterCreateTagsStatus(0, 1)

        count = self.importer.bulk_folders_create(frozenset({(str(subdir),)}), status)

        assert count == 1
        created = Folder.objects.get(library=self.inner_library, path=str(subdir))
        assert created.parent_folder == inner_folder

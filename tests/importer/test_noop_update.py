"""
Re-importing an unchanged comic writes nothing and reloads no browser.

Issue 992: a lazy import of a comic with no embedded tags re-read the
archive, found nothing new, and still rewrote the row, purged and rebuilt
its cover and broadcast LIBRARY_CHANGED. Every open browser reloaded. The
update phase now skips a comic whose tags, links, derived values and file
stat are all current, while Force Update still repairs a wrong link.
"""

import shutil
import zipfile
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.covers.tasks import CoverCreateTask
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import Comic, Genre, Library, Publisher, Universe
from codex.startup import codex_init
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir(Path(__file__).stem)
_PAGE: Final = b"\xff\xd8\xff\xe0not-a-real-jpeg"
_TAGS: Final = """comicbox:
  publisher:
    name: P
  series:
    name: S
  genres:
    Drama: {}
  universes:
    Alpha:
      designation: '1'
"""


class TestNoopUpdate(TestCase):
    """An unchanged comic skips the update; a changed one does not."""

    @override
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cache.clear()
        codex_init()

    @override
    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(TMP_DIR, ignore_errors=True)
        finally:
            super().tearDownClass()

    @override
    def setUp(self):
        cache.clear()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=TMP_DIR)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        cache.clear()

    @staticmethod
    def _write(name: str, tags: str | None, pages: int = 1) -> str:
        path = TMP_DIR / name
        with zipfile.ZipFile(path, "w") as zf:
            if tags is not None:
                zf.writestr("comicbox.yaml", tags)
            for page in range(pages):
                zf.writestr(f"page{page}.jpg", _PAGE)
        return str(path)

    def _import(self, task: ImportTask) -> MagicMock:
        """Run every import phase and finish; return the librarian queue."""
        queue = MagicMock()
        importer = ComicImporter(task, logger, queue, Lock(), Event())
        assert importer._run_per_comic_phases_chunked()  # noqa: SLF001
        importer.fail_imports()
        importer.delete()
        importer.full_text_search()
        importer.finish()
        return queue

    def _scan(self, path: str) -> None:
        self._import(
            ImportTask(library_id=self.library.pk, files_created=frozenset({path}))
        )

    def _force(self, path: str, *, check_metadata_mtime: bool = False) -> MagicMock:
        """Import the way Force Update (and, with the mtime check, Lazy) does."""
        return self._import(
            ImportTask(
                library_id=self.library.pk,
                files_modified=frozenset({path}),
                force_import_metadata=True,
                check_metadata_mtime=check_metadata_mtime,
            )
        )

    @staticmethod
    def _queued(queue: MagicMock) -> list:
        return [call.args[0] for call in queue.put.call_args_list]

    def _assert_untouched(self, path: str, queue: MagicMock, updated_at) -> None:
        queued = self._queued(queue)
        assert LIBRARY_CHANGED_TASK not in queued, queued
        assert not any(isinstance(task, CoverCreateTask) for task in queued), queued
        assert Comic.objects.get(path=path).updated_at == updated_at

    def test_lazy_import_of_tagless_comic_is_silent(self) -> None:
        """The reporter's case: hovering a comic with no tags file."""
        path = self._write("tagless.cbz", None)
        self._scan(path)
        updated_at = Comic.objects.get(path=path).updated_at

        queue = self._force(path, check_metadata_mtime=True)

        self._assert_untouched(path, queue, updated_at)

    def test_force_update_of_unchanged_comic_is_silent(self) -> None:
        """Force Update re-reads tags that turn out the same."""
        path = self._write("tagged.cbz", _TAGS)
        self._scan(path)
        updated_at = Comic.objects.get(path=path).updated_at

        queue = self._force(path)

        self._assert_untouched(path, queue, updated_at)

    def test_changed_file_still_updates(self) -> None:
        """New pages with the same tags still rewrite the row and the cover."""
        path = self._write("tagless.cbz", None)
        self._scan(path)
        updated_at = Comic.objects.get(path=path).updated_at
        self._write("tagless.cbz", None, pages=2)

        queue = self._force(path)

        queued = self._queued(queue)
        assert LIBRARY_CHANGED_TASK in queued
        assert any(isinstance(task, CoverCreateTask) for task in queued), queued
        comic = Comic.objects.get(path=path)
        assert comic.updated_at > updated_at
        assert comic.page_count == 2  # noqa: PLR2004

    def test_force_update_repairs_a_wrong_fk_link(self) -> None:
        """Force Update still relinks a comic whose file is unchanged."""
        path = self._write("tagged.cbz", _TAGS)
        self._scan(path)
        wrong = Publisher.objects.create(name="Wrong")
        Comic.objects.filter(path=path).update(publisher=wrong)
        updated_at = Comic.objects.get(path=path).updated_at

        queue = self._force(path)

        assert LIBRARY_CHANGED_TASK in self._queued(queue)
        comic = Comic.objects.get(path=path)
        assert comic.publisher.name == "P"
        assert comic.updated_at > updated_at

    def test_force_update_repairs_a_stray_m2m_link(self) -> None:
        """Force Update still unlinks a genre the file does not name."""
        path = self._write("tagged.cbz", _TAGS)
        self._scan(path)
        comic = Comic.objects.get(path=path)
        comic.genres.add(Genre.objects.create(name="Stray"))

        queue = self._force(path)

        assert LIBRARY_CHANGED_TASK in self._queued(queue)
        names = set(comic.genres.values_list("name", flat=True))
        assert names == {"Drama"}, names
        # The row write is what re-syncs its search entry and timestamp.
        assert Comic.objects.get(path=path).updated_at > comic.updated_at

    def test_force_update_of_a_tag_row_keeps_the_comic(self) -> None:
        """A corrected tag row reaches the browser through its comic's rewrite."""
        path = self._write("tagged.cbz", _TAGS)
        self._scan(path)
        Universe.objects.filter(name="Alpha").update(designation="9")
        updated_at = Comic.objects.get(path=path).updated_at

        queue = self._force(path)

        assert LIBRARY_CHANGED_TASK in self._queued(queue)
        assert Universe.objects.get(name="Alpha").designation == "1"
        assert Comic.objects.get(path=path).updated_at > updated_at

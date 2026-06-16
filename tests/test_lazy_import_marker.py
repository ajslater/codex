"""
The ``metadata_imported_at`` marker breaks the lazy-import hover loop.

``Comic.metadata_mtime`` is comicbox's *embedded* metadata mtime, which stays
NULL forever for an archive with no metadata file. The tag-icon hover gate and
the lazy-import worker used to key off ``metadata_mtime``, so a no-metadata comic
re-fired the importer endlessly. ``metadata_imported_at`` records that a forced
import pass actually ran, independent of embedded metadata:

* ``FinishImporter.finish`` stamps every comic a *forced* import touched (by
  path, so it covers the SKIPPED no-metadata comics that never reach the
  per-comic write path); a non-forced watcher import leaves the column alone.
* ``LazyImporter.lazy_import`` gates on ``metadata_imported_at__isnull=True``, so
  a comic is imported once and then excluded from further hover-triggered passes.
"""

import shutil
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.lazy_importer import LazyImporter
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume

_LIB_PATH: Final = Path("/tmp") / Path(__file__).stem  # noqa: S108
_COMIC_PATH: Final = str(_LIB_PATH / "bare.cbz")


class LazyImportMarkerTestCase(TestCase):
    """Stamp-at-finish and the lazy-import gate that reads the marker."""

    @override
    def setUp(self) -> None:
        """Seed admin flags and a single un-imported comic row."""
        from codex.startup import init_admin_flags

        cache.clear()
        init_admin_flags()
        # The Comic presave stats the file on disk, so it must exist.
        _LIB_PATH.mkdir(exist_ok=True)
        Path(_COMIC_PATH).write_bytes(b"")
        self.library = Library.objects.create(path=str(_LIB_PATH))  # pyright: ignore[reportUninitializedInstanceVariable]
        pub = Publisher.objects.create(name="Pub")
        imp = Imprint.objects.create(name="Imp", publisher=pub)
        ser = Series.objects.create(name="Ser", imprint=imp, publisher=pub)
        vol = Volume.objects.create(name="1", series=ser, imprint=imp, publisher=pub)
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library,
            path=_COMIC_PATH,
            issue_number=1,
            name="bare",
            publisher=pub,
            imprint=imp,
            series=ser,
            volume=vol,
            size=1,
            page_count=1,
        )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_LIB_PATH, ignore_errors=True)
        cache.clear()

    def _make_importer(self, *, force: bool) -> ComicImporter:
        task = ImportTask(
            library_id=self.library.pk,
            files_modified=frozenset({_COMIC_PATH}),
            force_import_metadata=force,
        )
        importer = ComicImporter(task, logger, MagicMock(), Lock(), Event())
        # apply() captures this before chunking zeros task.files_*; set it
        # directly since we drive finish() in isolation.
        importer.metadata_import_paths = frozenset({_COMIC_PATH})
        return importer

    @staticmethod
    def _enqueued_import_tasks(mock_queue) -> list[ImportTask]:
        return [
            call.args[0]
            for call in mock_queue.put.call_args_list
            if isinstance(call.args[0], ImportTask)
        ]

    def test_forced_finish_stamps_marker(self) -> None:
        """A forced import pass stamps the comic even with no metadata extracted."""
        assert self.comic.metadata_imported_at is None
        self._make_importer(force=True).finish()
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at is not None

    def test_non_forced_finish_leaves_marker_null(self) -> None:
        """An ordinary watcher import must not touch the marker."""
        self._make_importer(force=False).finish()
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at is None

    def test_stamp_is_idempotent(self) -> None:
        """A second forced pass does not move an already-set marker."""
        self._make_importer(force=True).finish()
        self.comic.refresh_from_db()
        first = self.comic.metadata_imported_at
        self._make_importer(force=True).finish()
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at == first

    def test_lazy_import_enqueues_when_marker_null(self) -> None:
        """An un-imported comic still triggers a forced lazy import."""
        queue = MagicMock()
        worker = LazyImporter(logger, queue, Lock())
        worker.lazy_import(
            LazyImportComicsTask(collection="comics", pks=frozenset({self.comic.pk}))
        )
        tasks = self._enqueued_import_tasks(queue)
        assert any(
            t.force_import_metadata and _COMIC_PATH in t.files_modified for t in tasks
        ), tasks

    def test_lazy_import_skips_already_marked(self) -> None:
        """Once the marker is set the gate enqueues nothing — the loop closes."""
        Comic.objects.filter(pk=self.comic.pk).update(
            metadata_imported_at=self.comic.created_at
        )
        queue = MagicMock()
        worker = LazyImporter(logger, queue, Lock())
        worker.lazy_import(
            LazyImportComicsTask(collection="comics", pks=frozenset({self.comic.pk}))
        )
        assert not self._enqueued_import_tasks(queue)

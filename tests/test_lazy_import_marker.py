"""
The ``metadata_imported_at`` marker breaks the lazy-import hover loop.

``Comic.metadata_mtime`` is comicbox's *embedded* metadata mtime, which stays
NULL forever for an archive with no metadata file. The tag-icon hover gate and
the lazy-import worker used to key off ``metadata_mtime``, so a no-metadata comic
re-fired the importer endlessly. ``metadata_imported_at`` records that a
tag-reading import pass actually ran, independent of embedded metadata:

* ``FinishImporter.finish`` stamps every comic a tag-reading import touched (by
  path, so it covers the SKIPPED no-metadata comics that never reach the
  per-comic write path). That is any forced import, and any library scan with
  the import-tags flag on; a scan with the flag off reads no tags and leaves the
  column NULL for the lazy importer.
* ``LazyImporter.lazy_import`` gates on ``metadata_imported_at__isnull=True``, so
  a comic is imported once and then excluded from further hover-triggered passes.
* Migration 0058 stamps the rows scans left NULL before scans stamped them.
"""

import importlib
import shutil
import zipfile
from pathlib import Path
from threading import Event, Lock
from typing import Final, override
from unittest.mock import MagicMock, patch

from django.apps import apps
from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.lazy_importer import LazyImporter
from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.admin import AdminFlag
from tests.tmp_dirs import tmp_dir

_MIGRATION = importlib.import_module("codex.migrations.0058_post_v2_5_5_schema")
_backfill = _MIGRATION._backfill_metadata_imported_at  # noqa: SLF001

_LIB_PATH: Final = tmp_dir(Path(__file__).stem)
_COMIC_PATH: Final = str(_LIB_PATH / "bare.cbz")
_SCAN_LIB_PATH: Final = tmp_dir(f"{Path(__file__).stem}-scan")


def _set_import_metadata_flag(*, on: bool) -> None:
    AdminFlag.objects.filter(key=AdminFlagChoices.IMPORT_METADATA.value).update(on=on)


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

    def test_forced_finish_stamps_marker_with_import_tags_off(self) -> None:
        """A forced pass reads tags whatever the scan flag says."""
        _set_import_metadata_flag(on=False)
        self._make_importer(force=True).finish()
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at is not None

    def test_scan_finish_stamps_marker_with_import_tags_on(self) -> None:
        """A scan that read tags stamps the comic, so hovers never re-import it."""
        self._make_importer(force=False).finish()
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at is not None

    def test_stamp_covers_every_batch(self) -> None:
        """A path set larger than one batch still stamps every comic."""
        other_path = str(_LIB_PATH / "other.cbz")
        Path(other_path).write_bytes(b"")
        other = Comic.objects.create(
            library=self.library,
            path=other_path,
            issue_number=2,
            name="other",
            publisher=self.comic.publisher,
            imprint=self.comic.imprint,
            series=self.comic.series,
            volume=self.comic.volume,
            size=1,
            page_count=1,
        )
        importer = self._make_importer(force=False)
        importer.metadata_import_paths = frozenset({_COMIC_PATH, other_path})
        with patch(
            "codex.librarian.scribe.importer.finish.IMPORTER_LINK_FK_BATCH_SIZE", 1
        ):
            importer.finish()
        for comic in (self.comic, other):
            comic.refresh_from_db()
            assert comic.metadata_imported_at is not None

    def test_scan_finish_leaves_marker_null_with_import_tags_off(self) -> None:
        """A scan that read no tags leaves the comic for the lazy importer."""
        _set_import_metadata_flag(on=False)
        self._make_importer(force=False).finish()
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at is None

    def test_backfill_stamps_with_import_tags_on(self) -> None:
        """0058 stamps the rows a tag-reading scan left NULL."""
        _backfill(apps, None)
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at == self.comic.updated_at

    def test_backfill_stamps_with_no_flag_row(self) -> None:
        """A missing flag row counts as its default, on."""
        AdminFlag.objects.filter(key=AdminFlagChoices.IMPORT_METADATA.value).delete()
        _backfill(apps, None)
        self.comic.refresh_from_db()
        assert self.comic.metadata_imported_at is not None

    def test_backfill_skips_with_import_tags_off(self) -> None:
        """0058 leaves the rows of a scan that read no tags to the lazy importer."""
        _set_import_metadata_flag(on=False)
        _backfill(apps, None)
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


class ScanStampsTaglessComicTestCase(TestCase):
    """Issue 992: a scanned comic with no tags file must not read as un-imported."""

    @override
    def setUp(self) -> None:
        """Seed admin flags, a library and a CBZ with pages but no tags."""
        from codex.startup import init_admin_flags

        cache.clear()
        init_admin_flags()
        _SCAN_LIB_PATH.mkdir(exist_ok=True, parents=True)
        self.path = str(_SCAN_LIB_PATH / "tagless.cbz")  # pyright: ignore[reportUninitializedInstanceVariable]
        with zipfile.ZipFile(self.path, "w") as zf:
            zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")
        self.library = Library.objects.create(path=str(_SCAN_LIB_PATH))  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_SCAN_LIB_PATH, ignore_errors=True)
        cache.clear()

    def test_scan_stamps_tagless_comic(self) -> None:
        """An ordinary scan creates the comic already stamped."""
        task = ImportTask(
            library_id=self.library.pk, files_created=frozenset({self.path})
        )
        importer = ComicImporter(task, logger, MagicMock(), Lock(), Event())
        assert importer._run_per_comic_phases_chunked()  # noqa: SLF001
        importer.finish()

        comic = Comic.objects.get(path=self.path)
        assert comic.metadata_mtime is None
        assert comic.metadata_imported_at is not None

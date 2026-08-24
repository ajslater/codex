"""
Tests for ``TagWriter`` comicbox-scheme file renaming.

Covers the rename pass and its watcher-aware DB sync: rename-only (no tag
patch) and tag-write-plus-rename, both enqueueing a targeted move
``ImportTask`` whether or not the library is watched, the in-place write a
watched library is left to notice for itself, the paths a recorded move
holds against a scan that lands mid-batch, and the skip-and-report
collision guard.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Final, Self, override
from unittest.mock import patch

from django.core.cache import caches
from django.test import TestCase
from loguru import logger

from codex.librarian.notifier.tasks import TAG_WRITE_ERRORS_CHANGED_TASK
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tagwrite_errors import get_tag_write_errors
from codex.librarian.scribe.tagwrite_moves import (
    clear_tag_write_moves,
    get_pending_tag_write_paths,
)
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import (
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_TMP_DIR: Final = Path("/tmp/codex.tests.tagrename")  # noqa: S108
_COMICBOX_TARGET: Final = "codex.librarian.scribe.tag_writer.Comicbox"
_TARGET_NAME: Final = "Renamed #001.cbz"


def _double(stub: object) -> Any:
    """Pass a test double through a concretely-typed seam."""
    return stub


class _FakeQueue:
    """Collects everything put on it for assertions."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class _FakeComicbox:
    """
    Stand-in for ``comicbox.box.Comicbox`` used by the rename pass.

    ``to_string(FILENAME)`` returns a fixed scheme name and ``rename_file``
    actually moves the file on disk (mirroring comicbox) so the real
    collision check, ``samefile``, and DB sync all run against the filesystem.
    """

    target: str = _TARGET_NAME

    def __init__(self, path, **_kwargs) -> None:
        self._path = Path(path)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def to_string(self, _fmt) -> str:
        return self.target

    def rename_file(self) -> None:
        new_path = self._path.parent / self.target
        self._path.rename(new_path)
        self._path = new_path

    def get_path(self) -> Path:
        return self._path


def _make_comic(*, events: bool, name: str = "c.cbz", read_only: bool = False) -> Comic:
    _TMP_DIR.mkdir(exist_ok=True, parents=True)
    library = Library.objects.create(
        path=str(_TMP_DIR), events=events, read_only=read_only
    )
    publisher = Publisher.objects.create(name="P")
    imprint = Imprint.objects.create(name="I", publisher=publisher)
    series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
    volume = Volume.objects.create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    path = _TMP_DIR / name
    path.write_text("comic")
    return Comic.objects.create(
        library=library,
        path=path,
        issue_number=1,
        name="c",
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        size=1,
        file_type="CBZ",
    )


def _make_writer(queue: _FakeQueue) -> TagWriter:
    """Build a TagWriter without the threading machinery."""
    writer = TagWriter.__new__(TagWriter)
    writer.log = _double(logger)
    writer.librarian_queue = _double(queue)
    return writer


class TagWriterRenameTests(TestCase):
    """The rename pass renames archives and syncs the DB, watcher-aware."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        clear_tag_write_moves()

    @override
    def tearDown(self) -> None:
        clear_tag_write_moves()
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_rename_only_unwatched_enqueues_move(self) -> None:
        """Rename-only in an unwatched library renames + enqueues a move task."""
        comic = _make_comic(events=False)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            writer.write_tags(task)

        new_path = old_path.parent / _TARGET_NAME
        assert new_path.exists()
        assert not old_path.exists()
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert imports[0].files_moved == {str(old_path): str(new_path)}
        # Rename-only: metadata unchanged, so no re-read is requested.
        assert imports[0].files_modified == frozenset()
        assert imports[0].force_import_metadata is True

    def test_read_only_library_is_never_renamed(self) -> None:
        """A read-only comic is not renamed even if a task carries its pk."""
        comic = _make_comic(events=False, read_only=True)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            writer.write_tags(task)

        # File untouched and nothing enqueued: the read-only exclusion drops it
        # before the rename pass ever runs.
        assert old_path.exists()
        assert not (old_path.parent / _TARGET_NAME).exists()
        assert not queue.items

    def test_rename_only_watched_enqueues_move(self) -> None:
        """A watched library's rename is recorded by codex, not left to the watcher."""
        comic = _make_comic(events=True)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            writer.write_tags(task)

        new_path = old_path.parent / _TARGET_NAME
        assert new_path.exists()
        # The watcher's inode pairing is best-effort, so codex states the
        # move it performed. A move the watcher also pairs is deduplicated
        # downstream by the occupied-destination guard.
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert imports[0].files_moved == {str(old_path): str(new_path)}
        # Rename-only: metadata unchanged, so no re-read is requested.
        assert imports[0].files_modified == frozenset()
        # Both ends are held until that move is applied, so a scan landing
        # first can't reconcile them out from under it.
        assert get_pending_tag_write_paths() == frozenset(
            {str(old_path), str(new_path)}
        )

    def test_tag_write_and_rename_watched_enqueues_move_and_reread(self) -> None:
        """
        A watched write + rename records the move and re-reads the new path.

        This is the PDF case: pdffile's save() writes a temp file and
        ``replace()``s it over the original, so the renamed file carries a
        new inode and the watcher can never pair it to the row's stored one.
        """
        comic = _make_comic(events=True)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}),
            patch={"series": {"name": "S"}},
            rename=True,
        )

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch.object(
                TagWriter,
                "_collect_written_paths",
                return_value={comic.pk: old_path},
            ),
        ):
            writer.write_tags(task)

        new_path = old_path.parent / _TARGET_NAME
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert imports[0].files_moved == {str(old_path): str(new_path)}
        assert imports[0].files_modified == frozenset({str(new_path)})
        assert get_pending_tag_write_paths() == frozenset(
            {str(old_path), str(new_path)}
        )

    def test_write_only_watched_enqueues_nothing(self) -> None:
        """An in-place write with no rename is still left to the watcher."""
        comic = _make_comic(events=True)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}), patch={"series": {"name": "S"}}
        )

        with patch.object(
            TagWriter,
            "_collect_written_paths",
            return_value={comic.pk: old_path},
        ):
            writer.write_tags(task)

        # The path never changed, so there is no move to state; the
        # watcher's modify event carries the re-read.
        assert not [i for i in queue.items if isinstance(i, ImportTask)]
        assert not get_pending_tag_write_paths()

    def test_collision_skips_and_reports(self) -> None:
        """A target collision skips the rename and records a tag-write error."""
        comic = _make_comic(events=False)
        old_path = Path(comic.path)
        # Pre-create a *different* file at the target name.
        (old_path.parent / _TARGET_NAME).write_text("other")
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            writer.write_tags(task)

        # Original untouched, no move enqueued, error surfaced.
        assert old_path.exists()
        assert not [i for i in queue.items if isinstance(i, ImportTask)]
        assert TAG_WRITE_ERRORS_CHANGED_TASK in queue.items
        errors = get_tag_write_errors()
        assert errors
        assert errors[0]["path"] == str(old_path)

    def test_no_change_when_name_matches(self) -> None:
        """When the scheme name equals the current name, nothing happens."""
        comic = _make_comic(events=False, name=_TARGET_NAME)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            writer.write_tags(task)

        assert old_path.exists()
        assert not [i for i in queue.items if isinstance(i, ImportTask)]

    def test_tag_write_and_rename_unwatched_rereads_metadata(self) -> None:
        """A tag write + rename re-reads metadata for the new path (unwatched)."""
        comic = _make_comic(events=False)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}),
            patch={"series": {"name": "S"}},
            rename=True,
        )

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch.object(
                TagWriter,
                "_collect_written_paths",
                return_value={comic.pk: old_path},
            ),
        ):
            writer.write_tags(task)

        new_path = old_path.parent / _TARGET_NAME
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert imports[0].files_moved == {str(old_path): str(new_path)}
        # Tags were written, so the new path is re-read.
        assert imports[0].files_modified == frozenset({str(new_path)})


class TagWriterConversionTests(TestCase):
    """
    A tag write that converts the archive (CBR -> CBZ) syncs the DB.

    Comicbox repacks unwritable archives as CBZ during a write and reports
    the new file as the result's ``final_path``. The converted archive is a
    new inode, which neither the watcher nor the poller can pair into a
    move, so codex must record the move itself — for watched libraries too
    — and the rename pass must chase the file to its converted path.
    """

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        clear_tag_write_moves()

    @override
    def tearDown(self) -> None:
        clear_tag_write_moves()
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _convert(old_path: Path) -> Path:
        """Simulate comicbox's CBR->CBZ conversion with delete_orig."""
        new_path = old_path.with_suffix(".cbz")
        old_path.rename(new_path)
        return new_path

    def _write_task(self, comic: Comic) -> BulkTagWriteTask:
        return BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}),
            patch={"series": {"name": "S"}},
            delete_original=True,
            rename=True,
        )

    def test_converted_write_renames_the_cbz_and_enqueues_move(self) -> None:
        """Rename follows the conversion; one move from the DB path lands."""
        comic = _make_comic(events=False, name="c.cbr")
        old_path = Path(comic.path)
        cbz_path = self._convert(old_path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = self._write_task(comic)

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch.object(
                TagWriter,
                "_collect_written_paths",
                return_value={comic.pk: cbz_path},
            ),
        ):
            writer.write_tags(task)

        renamed_path = old_path.parent / _TARGET_NAME
        assert renamed_path.exists()
        assert not cbz_path.exists()
        assert not old_path.exists()
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        # The move source is the DB's path (the dead .cbr), not the interim cbz.
        assert imports[0].files_moved == {str(old_path): str(renamed_path)}
        assert imports[0].files_modified == frozenset({str(renamed_path)})
        # Every path the move passes through is held against a scan that
        # lands before the move task does.
        assert get_pending_tag_write_paths() == frozenset(
            {str(old_path), str(cbz_path), str(renamed_path)}
        )

    def test_converted_write_without_rename_enqueues_move(self) -> None:
        """Conversion alone moves the DB row onto the new cbz."""
        comic = _make_comic(events=False, name="c.cbr")
        old_path = Path(comic.path)
        cbz_path = self._convert(old_path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = self._write_task(comic)
        task.rename = False

        with patch.object(
            TagWriter,
            "_collect_written_paths",
            return_value={comic.pk: cbz_path},
        ):
            writer.write_tags(task)

        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert imports[0].files_moved == {str(old_path): str(cbz_path)}
        assert imports[0].files_modified == frozenset({str(cbz_path)})

    def test_converted_write_watched_still_enqueues_move(self) -> None:
        """Watched libraries can't inode-pair a conversion; codex enqueues it."""
        comic = _make_comic(events=True, name="c.cbr")
        old_path = Path(comic.path)
        cbz_path = self._convert(old_path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = self._write_task(comic)

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch.object(
                TagWriter,
                "_collect_written_paths",
                return_value={comic.pk: cbz_path},
            ),
        ):
            writer.write_tags(task)

        renamed_path = old_path.parent / _TARGET_NAME
        assert renamed_path.exists()
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert imports[0].files_moved == {str(old_path): str(renamed_path)}

    def test_converted_write_keeping_original_creates_not_moves(self) -> None:
        """Without delete_original the DB comic is untouched; cbz is new."""
        comic = _make_comic(events=False, name="c.cbr")
        old_path = Path(comic.path)
        # Original kept: the cbz appears alongside it.
        cbz_path = old_path.with_suffix(".cbz")
        shutil.copyfile(old_path, cbz_path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = self._write_task(comic)
        task.delete_original = False
        task.rename = False

        with patch.object(
            TagWriter,
            "_collect_written_paths",
            return_value={comic.pk: cbz_path},
        ):
            writer.write_tags(task)

        assert old_path.exists()
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert not imports[0].files_moved
        assert imports[0].files_created == frozenset({str(cbz_path)})
        assert imports[0].files_modified == frozenset()
        # Nothing moved, so nothing needs holding back from a scan.
        assert not get_pending_tag_write_paths()

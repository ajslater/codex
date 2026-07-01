"""
Tests for ``TagWriter`` comicbox-scheme file renaming.

Covers the rename pass and its watcher-aware DB sync: rename-only (no tag
patch) and tag-write-plus-rename, the unwatched (codex enqueues a targeted
move ``ImportTask``) vs watched (the watcher owns it, codex enqueues nothing)
branch, and the skip-and-report collision guard.
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


def _make_comic(*, events: bool, name: str = "c.cbz") -> Comic:
    _TMP_DIR.mkdir(exist_ok=True, parents=True)
    library = Library.objects.create(path=str(_TMP_DIR), events=events)
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

    @override
    def tearDown(self) -> None:
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

    def test_rename_only_watched_enqueues_nothing(self) -> None:
        """A watched library's rename is left to the watcher; codex stays quiet."""
        comic = _make_comic(events=True)
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        task = BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            writer.write_tags(task)

        # File still renamed on disk, but no ImportTask: the watcher's
        # move-detection will pick it up.
        assert (old_path.parent / _TARGET_NAME).exists()
        assert not [i for i in queue.items if isinstance(i, ImportTask)]

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
            patch.object(TagWriter, "_collect_written_pks", return_value={comic.pk}),
        ):
            writer.write_tags(task)

        new_path = old_path.parent / _TARGET_NAME
        imports = [i for i in queue.items if isinstance(i, ImportTask)]
        assert len(imports) == 1
        assert imports[0].files_moved == {str(old_path): str(new_path)}
        # Tags were written, so the new path is re-read.
        assert imports[0].files_modified == frozenset({str(new_path)})

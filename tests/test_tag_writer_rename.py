"""
Tests for ``TagWriter``'s rename-first flow and its inline database sync.

Renaming happens before the write, and every move it causes is applied to
the database before ``write_tags`` returns. That ordering is the whole
point: no scan can be processed while the database disagrees with the
disk, so a comic keeps its bookmarks through a rename, a conversion, or
both. What remains queued is only the metadata re-read, which names a path
the database already holds.
"""

from __future__ import annotations

import shutil
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path
from threading import Event, Lock
from typing import Any, Final, Self, override
from unittest.mock import patch

from django.core.cache import caches
from django.test import TestCase
from loguru import logger

from codex.librarian.notifier.tasks import TAG_WRITE_ERRORS_CHANGED_TASK
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tagwrite_errors import get_tag_write_errors
from codex.librarian.scribe.tagwrite_rename import build_predict_config, plan_rename
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_TMP_DIR: Final = Path("/tmp/codex.tests.tagrename")  # noqa: S108
_COMICBOX_TARGET: Final = "codex.librarian.scribe.tagwrite_rename.Comicbox"
_TARGET_NAME: Final = "Renamed #001.cbz"
_EXAMPLE_CBZ: Final = Path(__file__).parent / "files" / "comicbox-2-example.cbz"
#: One comic renames, the other keeps its own path.
_DISTINCT_PATHS: Final = 2


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
    Stand-in for ``comicbox.box.Comicbox`` used by rename prediction.

    ``predict_filename`` returns a fixed scheme name, keeping the source
    archive's suffix as the real one does. Codex performs the rename, so
    the fake never touches the filesystem — the collision checks,
    ``samefile``, and the database sync all run for real.
    """

    stem: str = Path(_TARGET_NAME).stem

    def __init__(self, path, **_kwargs) -> None:
        self._path = Path(path)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def predict_filename(self) -> str:
        return f"{self.stem}{self._path.suffix}"


def _make_library(*, events: bool, read_only: bool = False) -> Library:
    _TMP_DIR.mkdir(exist_ok=True, parents=True)
    return Library.objects.create(
        path=str(_TMP_DIR), events=events, read_only=read_only
    )


def _make_comic(
    *,
    events: bool,
    name: str = "c.cbz",
    read_only: bool = False,
    library: Library | None = None,
    issue_number: int = 1,
) -> Comic:
    library = library or _make_library(events=events, read_only=read_only)
    publisher, _ = Publisher.objects.get_or_create(name="P")
    imprint, _ = Imprint.objects.get_or_create(name="I", publisher=publisher)
    series, _ = Series.objects.get_or_create(
        name="S", publisher=publisher, imprint=imprint
    )
    volume, _ = Volume.objects.get_or_create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    folder, _ = Folder.objects.get_or_create(
        library=library, path=str(_TMP_DIR), defaults={"name": _TMP_DIR.name}
    )
    path = _TMP_DIR / name
    path.write_text("comic")
    comic = Comic.objects.create(
        library=library,
        path=path,
        parent_folder=folder,
        issue_number=issue_number,
        name=path.stem,
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        size=1,
        file_type="CBZ",
    )
    comic.folders.add(folder)
    return comic


def _make_writer(queue: _FakeQueue) -> TagWriter:
    """Build a TagWriter without the threading machinery."""
    writer = TagWriter.__new__(TagWriter)
    writer.log = _double(logger)
    writer.librarian_queue = _double(queue)
    writer.db_write_lock = _double(Lock())
    writer.abort_event = _double(Event())
    return writer


def _imports(queue: _FakeQueue) -> list[ImportTask]:
    return [i for i in queue.items if isinstance(i, ImportTask)]


class TagWriterRenameFirstTests(TestCase):
    """The rename lands on disk and in the database before the write."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _rename_only(comic: Comic) -> BulkTagWriteTask:
        return BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)

    def test_rename_moves_the_row_before_returning(self) -> None:
        """The database holds the new path by the time write_tags returns."""
        comic = _make_comic(events=False)
        old_path = Path(comic.path)
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(self._rename_only(comic))

        new_path = old_path.parent / _TARGET_NAME
        assert new_path.exists()
        assert not old_path.exists()
        comic.refresh_from_db()
        assert comic.path == str(new_path)
        # No move task is queued: there is nothing left for the importer to
        # reconcile, which is what makes a racing scan harmless.
        assert all(not i.files_moved for i in _imports(queue))

    def test_a_watched_library_is_synced_the_same_way(self) -> None:
        """Watcher pairing is unreliable, so codex never depends on it."""
        comic = _make_comic(events=True)
        old_path = Path(comic.path)
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(self._rename_only(comic))

        comic.refresh_from_db()
        assert comic.path == str(old_path.parent / _TARGET_NAME)

    def test_rename_only_asks_for_no_reread(self) -> None:
        """A rename changes no metadata, so nothing needs re-reading."""
        comic = _make_comic(events=False)
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(self._rename_only(comic))

        assert not _imports(queue)

    def test_the_row_keeps_its_identity(self) -> None:
        """The row is moved, not replaced, so its bookmarks survive."""
        comic = _make_comic(events=False)
        pk = comic.pk
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(self._rename_only(comic))

        assert Comic.objects.filter(pk=pk).exists()

    def test_a_second_write_resolves_the_new_path(self) -> None:
        """
        A follow-up edit sees the renamed path, not the pre-rename one.

        The database used to be synced by a queued task that a second
        tag-write outranked, so the second write opened a path that no
        longer existed and dropped the user's edit.
        """
        comic = _make_comic(events=False)
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            writer = _make_writer(queue)
            writer.write_tags(self._rename_only(comic))
            resolved, _ = writer._resolve_comics(  # noqa: SLF001
                self._rename_only(comic)
            )

        new_path = _TMP_DIR / _TARGET_NAME
        assert resolved[comic.pk] == new_path
        assert resolved[comic.pk].exists()

    def test_read_only_library_is_never_renamed(self) -> None:
        """A read-only comic is untouched even if a task carries its pk."""
        comic = _make_comic(events=False, read_only=True)
        old_path = Path(comic.path)
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(self._rename_only(comic))

        assert old_path.exists()
        assert not (old_path.parent / _TARGET_NAME).exists()
        assert not queue.items

    def test_no_change_when_the_name_already_matches(self) -> None:
        """Nothing happens when the scheme name is the current name."""
        comic = _make_comic(events=False, name=_TARGET_NAME)
        old_path = Path(comic.path)
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(self._rename_only(comic))

        assert old_path.exists()
        assert not _imports(queue)


class TagWriterRenameCollisionTests(TestCase):
    """Destinations that aren't free are skipped and reported."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_existing_file_at_the_target_skips_the_rename(self) -> None:
        """An unrelated file already at the name is never clobbered."""
        comic = _make_comic(events=False)
        old_path = Path(comic.path)
        (old_path.parent / _TARGET_NAME).write_text("other")
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(
                BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)
            )

        assert old_path.exists()
        assert (old_path.parent / _TARGET_NAME).read_text() == "other"
        comic.refresh_from_db()
        assert comic.path == str(old_path)
        assert TAG_WRITE_ERRORS_CHANGED_TASK in queue.items
        assert get_tag_write_errors()

    def test_two_comics_predicting_one_name_keep_the_first(self) -> None:
        """A batch-internal collision costs one rename, not the archive."""
        library = _make_library(events=False)
        first = _make_comic(events=False, name="a.cbz", library=library)
        second = _make_comic(
            events=False, name="b.cbz", library=library, issue_number=2
        )
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(
                BulkTagWriteTask(
                    comic_pks=frozenset({first.pk, second.pk}), rename=True
                )
            )

        renamed = _TMP_DIR / _TARGET_NAME
        assert renamed.exists()
        # Exactly one of them moved; the other kept its file and its row.
        paths = {
            Comic.objects.get(pk=first.pk).path,
            Comic.objects.get(pk=second.pk).path,
        }
        assert str(renamed) in paths
        assert len(paths) == _DISTINCT_PATHS
        assert get_tag_write_errors()

    def test_a_target_another_comic_holds_is_skipped(self) -> None:
        """A name the database already assigns elsewhere is refused."""
        library = _make_library(events=False)
        comic = _make_comic(events=False, name="a.cbz", library=library)
        _make_comic(events=False, name=_TARGET_NAME, library=library, issue_number=2)
        old_path = Path(comic.path)
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(
                BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)
            )

        comic.refresh_from_db()
        assert comic.path == str(old_path)
        assert old_path.exists()


class TagWriterConversionTests(TestCase):
    """A conversion moves the file after the write, and is synced then."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _convert(source: Path) -> Path:
        """Stand in for comicbox repacking an unwritable archive."""
        new_path = source.with_suffix(".cbz")
        source.rename(new_path)
        return new_path

    def test_conversion_moves_the_row_to_the_cbz(self) -> None:
        """Rename first, then the conversion move, both applied inline."""
        comic = _make_comic(events=False, name="c.cbr")
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)
        renamed = old_path.parent / f"{Path(_TARGET_NAME).stem}.cbr"
        converted = renamed.with_suffix(".cbz")

        def fake_write(_self, _task, current_paths):
            # The write repacks whatever the rename left behind.
            assert current_paths[comic.pk] == renamed
            return {comic.pk: self._convert(current_paths[comic.pk])}

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch.object(TagWriter, "_write", fake_write),
        ):
            writer.write_tags(
                BulkTagWriteTask(
                    comic_pks=frozenset({comic.pk}),
                    patch={"series": {"name": "S"}},
                    delete_original=True,
                    rename=True,
                )
            )

        assert converted.exists()
        assert not old_path.exists()
        comic.refresh_from_db()
        assert comic.path == str(converted)
        # Only the re-read is left queued, and it names the row's own path.
        imports = _imports(queue)
        assert len(imports) == 1
        assert not imports[0].files_moved
        assert imports[0].files_modified == frozenset({str(converted)})

    def test_keeping_the_original_leaves_the_row_alone(self) -> None:
        """The row stays on the original; the CBZ is reported as new."""
        comic = _make_comic(events=False, name="c.cbr")
        old_path = Path(comic.path)
        queue = _FakeQueue()
        writer = _make_writer(queue)

        def fake_write(_self, _task, current_paths):
            source = current_paths[comic.pk]
            new_path = source.with_suffix(".cbz")
            new_path.write_text("converted")
            return {comic.pk: new_path}

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch.object(TagWriter, "_write", fake_write),
        ):
            writer.write_tags(
                BulkTagWriteTask(
                    comic_pks=frozenset({comic.pk}),
                    patch={"series": {"name": "S"}},
                    delete_original=False,
                    rename=True,
                )
            )

        # The original is untouched, so its row never moved.
        assert old_path.exists()
        comic.refresh_from_db()
        assert comic.path == str(old_path)
        # The new CBZ got the scheme name and is imported as a new comic.
        renamed_cbz = old_path.parent / _TARGET_NAME
        assert renamed_cbz.exists()
        imports = _imports(queue)
        assert len(imports) == 1
        assert imports[0].files_created == frozenset({str(renamed_cbz)})
        assert not imports[0].files_moved


class TagWriterInPlaceWriteTests(TestCase):
    """A write that moves nothing still gets its metadata re-read."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _write_in_place(self, comic: Comic, queue: _FakeQueue) -> None:
        old_path = Path(comic.path)
        with patch.object(TagWriter, "_write", lambda *_args: {comic.pk: old_path}):
            _make_writer(queue).write_tags(
                BulkTagWriteTask(
                    comic_pks=frozenset({comic.pk}), patch={"series": {"name": "S"}}
                )
            )

    def test_unwatched_in_place_write_is_reread(self) -> None:
        """An unwatched library has no scanner to notice the write."""
        comic = _make_comic(events=False)
        queue = _FakeQueue()

        self._write_in_place(comic, queue)

        imports = _imports(queue)
        assert len(imports) == 1
        assert imports[0].files_modified == frozenset({str(comic.path)})
        assert imports[0].force_import_metadata is True

    def test_watched_in_place_write_is_reread_too(self) -> None:
        """The watcher's own re-read is stat-only when the flag is off."""
        comic = _make_comic(events=True)
        queue = _FakeQueue()

        self._write_in_place(comic, queue)

        imports = _imports(queue)
        assert len(imports) == 1
        assert imports[0].files_modified == frozenset({str(comic.path)})


class TagWriterRenamePlanTests(TestCase):
    """The plan names both the interim and the final path."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _make_cbt(path: Path) -> None:
        """Repack the example CBZ as a tarball: a real un-writable archive."""
        with zipfile.ZipFile(_EXAMPLE_CBZ) as zf, tarfile.open(path, "w") as tf:
            for name in zf.namelist():
                data = zf.read(name)
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, BytesIO(data))

    def test_a_converting_archive_plans_both_paths(self) -> None:
        """The interim rename keeps .cbt; the write's output is the .cbz."""
        old_path = _TMP_DIR / "Rename Me v1999 #001 (1999).cbt"
        self._make_cbt(old_path)

        plan = plan_rename(1, old_path, None, build_predict_config((), "additive"))

        assert plan is not None
        assert plan.target.suffix == ".cbt"
        assert plan.final_path.suffix == ".cbz"
        assert plan.final_path.stem == plan.target.stem

    def test_a_cbz_plans_one_path(self) -> None:
        """Nothing to convert, so the rename target is the final path."""
        old_path = _TMP_DIR / "Rename Me v1999 #002 (1999).cbz"
        shutil.copy(_EXAMPLE_CBZ, old_path)

        plan = plan_rename(1, old_path, None, build_predict_config((), "additive"))

        assert plan is not None
        assert plan.target == plan.final_path
        assert plan.target.suffix == ".cbz"


class TagWriterRenameEdgeCaseTests(TestCase):
    """The awkward cases: same file, different name; and a refused move."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_case_only_rename_is_allowed(self) -> None:
        """
        Renaming only the case of a name is a real rename, not a collision.

        On a case-insensitive filesystem the destination already "exists" —
        as the very file being renamed — so the collision check has to ask
        whether it is the same file, not merely whether something is there.
        """
        comic = _make_comic(events=False, name=_TARGET_NAME.lower())
        queue = _FakeQueue()

        with patch(_COMICBOX_TARGET, _FakeComicbox):
            _make_writer(queue).write_tags(
                BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)
            )

        comic.refresh_from_db()
        assert comic.path == str(_TMP_DIR / _TARGET_NAME)
        assert not get_tag_write_errors()

    def test_a_refused_database_move_puts_the_file_back(self) -> None:
        """
        Disk and database never disagree, even when the move is refused.

        The move phase drops a move it can't apply, which would otherwise
        leave the row pointing at a path that no longer exists — the exact
        state a later scan turns into a delete.
        """
        comic = _make_comic(events=False)
        old_path = Path(comic.path)
        queue = _FakeQueue()

        with (
            patch(_COMICBOX_TARGET, _FakeComicbox),
            patch(
                "codex.librarian.scribe.tag_writer.ComicImporter.bulk_comics_moved",
                return_value=0,
            ),
        ):
            _make_writer(queue).write_tags(
                BulkTagWriteTask(comic_pks=frozenset({comic.pk}), rename=True)
            )

        assert old_path.exists()
        assert not (_TMP_DIR / _TARGET_NAME).exists()
        comic.refresh_from_db()
        assert comic.path == str(old_path)
        assert get_tag_write_errors()

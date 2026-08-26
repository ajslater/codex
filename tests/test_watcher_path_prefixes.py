"""
Watcher path matching must respect directory boundaries.

Both the deleted-directory expansion and the library attributor matched a
bare string prefix, so any two paths where one name starts with the other
("Batman" / "Batman Beyond") were treated as parent and child. Expanding a
delete that way destroys a sibling tree's comics — and their bookmarks —
while the files are still on disk.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final, override

from django.test import TestCase

from codex.librarian.fs.events import FSChange
from codex.librarian.fs.watcher.data import ChangeBatch
from codex.librarian.fs.watcher.dirs import expand_dir_deleted
from codex.librarian.fs.watcher.events import _find_library
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_ROOT: Final = Path("/tmp/codex.tests.watcherprefix")  # noqa: S108
_MAIN_PK: Final = 1
_KIDS_PK: Final = 2


class FindLibraryPrefixTests(TestCase):
    """Events belong to the library that actually contains them."""

    def test_sibling_library_prefix_does_not_capture_events(self) -> None:
        """A sibling root sharing a name prefix never claims the other's events."""
        library_paths = {"/comics": _MAIN_PK, "/comics-kids": _KIDS_PK}

        assert _find_library(library_paths, "/comics-kids/x.cbz") == _KIDS_PK
        assert _find_library(library_paths, "/comics/x.cbz") == _MAIN_PK

    def test_library_root_itself_matches(self) -> None:
        """An event on the root directory still belongs to that library."""
        assert _find_library({"/comics": _MAIN_PK}, "/comics") == _MAIN_PK

    def test_unrelated_path_matches_nothing(self) -> None:
        """A path outside every library root is unattributed."""
        assert _find_library({"/comics": _MAIN_PK}, "/comics-kids") is None
        assert _find_library({"/comics": _MAIN_PK}, "/elsewhere/x.cbz") is None


class ExpandDirDeletedTests(TestCase):
    """Deleting a directory only expands to its own children."""

    @override
    def setUp(self) -> None:
        _ROOT.mkdir(parents=True, exist_ok=True)
        self.library = Library.objects.create(path=str(_ROOT))  # pyright: ignore[reportUninitializedInstanceVariable]
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        self.fks = {  # pyright: ignore[reportUninitializedInstanceVariable]
            "publisher": publisher,
            "imprint": imprint,
            "series": series,
            "volume": volume,
        }

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_ROOT, ignore_errors=True)

    def _make_folder(self, path: Path) -> Folder:
        path.mkdir(parents=True, exist_ok=True)
        return Folder.objects.create(
            library=self.library, path=str(path), name=path.name
        )

    def _make_comic(self, path: Path) -> Comic:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("comic")
        return Comic.objects.create(
            library=self.library,
            path=str(path),
            issue_number=1,
            name=path.stem,
            size=1,
            file_type="CBZ",
            **self.fks,
        )

    def test_sibling_prefix_tree_is_untouched(self) -> None:
        """Deleting /Batman must not expand into /Batman Beyond."""
        target = _ROOT / "Batman"
        sibling = _ROOT / "Batman Beyond"
        self._make_folder(target)
        self._make_folder(sibling)
        target_comic = self._make_comic(target / "a.cbz")
        sibling_comic = self._make_comic(sibling / "b.cbz")

        batch = ChangeBatch()
        expand_dir_deleted(str(target), self.library.pk, batch)

        deleted_files = {event.src_path for _, event in batch.deleted}
        deleted_dirs = {event.src_path for _, event in batch.dir_deleted}
        assert deleted_files == {target_comic.path}
        assert sibling_comic.path not in deleted_files
        assert deleted_dirs == {str(target)}
        assert str(sibling) not in deleted_dirs

    def test_real_children_are_expanded(self) -> None:
        """Nested folders and their comics are still collected."""
        target = _ROOT / "Batman"
        child = target / "Year One"
        self._make_folder(target)
        self._make_folder(child)
        comic = self._make_comic(child / "a.cbz")

        batch = ChangeBatch()
        expand_dir_deleted(str(target), self.library.pk, batch)

        assert {event.src_path for _, event in batch.deleted} == {comic.path}
        assert {event.src_path for _, event in batch.dir_deleted} == {
            str(target),
            str(child),
        }
        assert all(event.change == FSChange.deleted for _, event in batch.dir_deleted)

    def test_directory_is_listed_once(self) -> None:
        """The deleted directory's own row must not be emitted twice."""
        target = _ROOT / "Batman"
        self._make_folder(target)

        batch = ChangeBatch()
        expand_dir_deleted(str(target), self.library.pk, batch)

        paths = [event.src_path for _, event in batch.dir_deleted]
        assert paths == [str(target)]

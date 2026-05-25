"""Ignore-pattern filtering across the librarian's fs walker, watcher, and helpers."""

from __future__ import annotations

import shutil
from logging import getLogger
from pathlib import Path
from typing import Final
from unittest.mock import patch

import pytest
from watchfiles import Change

from codex.librarian.fs import filters as filters_mod
from codex.librarian.fs.filters import is_ignored_basename, is_ignored_path
from codex.librarian.fs.poller.snapshot import DiskSnapshot
from codex.librarian.fs.watcher.data import ChangeBatch
from codex.librarian.fs.watcher.dirs import expand_dir_added
from codex.librarian.fs.watcher.watcher import CodexWatchFilter

_TEST_LIB_ROOT: Final = Path("/tmp/codex.tests.fs_ignore")  # noqa: S108


class TestIsIgnoredPath:
    """Component-level check used by the watcher and walker."""

    def test_plain_path_is_not_ignored(self) -> None:
        assert is_ignored_path(Path("/lib/comics/foo.cbz")) is False

    def test_dotfile_basename(self) -> None:
        assert is_ignored_path(Path("/lib/comics/.DS_Store")) is True

    def test_dotfile_ancestor_directory(self) -> None:
        # ``.git/HEAD`` — basename is innocuous, but ``.git`` makes the
        # whole subtree hidden.
        assert is_ignored_path(Path("/lib/comics/.git/HEAD")) is True

    def test_root_components_skipped_when_root_supplied(self) -> None:
        # The library root may itself live under a hidden parent.
        # The check is relative to ``root`` so the library still polls.
        root = "/Users/aj/.archive"
        assert is_ignored_path(Path(f"{root}/comic.cbz"), root=root) is False

    def test_folder_cover_dotfile_passes(self) -> None:
        # ``.codex-cover.jpg`` looks like a hidden file but is the
        # user-supplied per-folder cover. The dotfile filter must let
        # it through so the cover importer can claim it.
        assert is_ignored_path(Path("/lib/comics/series/.codex-cover.jpg")) is False
        assert is_ignored_basename(".codex-cover.jpg") is False
        assert is_ignored_basename(".codex-cover.webp") is False
        assert is_ignored_basename(".codex-cover.png") is False

    def test_folder_cover_dotfile_without_image_ext_still_ignored(self) -> None:
        # ``.codex-cover`` (no extension) or non-image extensions are
        # not real folder covers — keep them filtered as ordinary
        # dotfiles.
        assert is_ignored_basename(".codex-cover") is True
        assert is_ignored_basename(".codex-cover.txt") is True

    def test_subtree_ignored_still_caught_with_root(self) -> None:
        root = "/Users/aj/.archive"
        path = Path(f"{root}/.tmp/comic.cbz")
        assert is_ignored_path(path, root=root) is True

    def test_unrelated_root_falls_back_to_full_path(self) -> None:
        # When ``relative_to`` raises, the helper checks the whole path,
        # not the relativized fragment. ``.git`` anywhere still counts.
        assert is_ignored_path(Path("/lib/.git/HEAD"), root="/other") is True


class TestRegistryExtensibility:
    """Adding a basename to the registry propagates everywhere."""

    def test_exact_basename_registry_picked_up(self) -> None:
        # Proves the registry is the single source of truth: extending
        # ``_IGNORED_BASENAMES`` makes both ``is_ignored_basename`` and
        # ``is_ignored_path`` skip the pattern without any caller-site
        # edits to the walker or watcher.
        new_set = frozenset({"@eaDir"})
        with patch.object(filters_mod, "_IGNORED_BASENAMES", new_set):
            assert is_ignored_basename("@eaDir") is True
            assert is_ignored_path(Path("/lib/comics/@eaDir/thumb.jpg")) is True
            # Unrelated names still pass.
            assert is_ignored_basename("comic.cbz") is False

    def test_prefix_registry_picked_up(self) -> None:
        with patch.object(filters_mod, "_IGNORED_BASENAME_PREFIXES", ("#",)):
            # Prefix-only run: dotfiles no longer match.
            assert is_ignored_basename("#recycle") is True
            assert is_ignored_basename(".DS_Store") is False


class TestDiskSnapshotSkipsDotfiles:
    """The poller's walker must not surface dotfile paths."""

    @pytest.fixture(autouse=True)
    def _tmp_library(self):
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)
        _TEST_LIB_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)

    def test_dotfile_file_skipped(self) -> None:
        (_TEST_LIB_ROOT / "comic.cbz").touch()
        (_TEST_LIB_ROOT / ".DS_Store").touch()
        snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"), covers_only=False)
        names = {Path(p).name for p in snap.paths}
        assert "comic.cbz" in names
        assert ".DS_Store" not in names

    def test_dotfile_directory_pruned(self) -> None:
        (_TEST_LIB_ROOT / "comic.cbz").touch()
        dot_dir = _TEST_LIB_ROOT / ".git"
        dot_dir.mkdir()
        (dot_dir / "HEAD").touch()
        (dot_dir / "config").touch()
        snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"), covers_only=False)
        # Neither the dot-dir nor any descendant should appear.
        assert not any(".git" in Path(p).parts for p in snap.paths)

    def test_folder_cover_dotfile_picked_up(self) -> None:
        # Regression: the dotfile filter used to swallow user-supplied
        # ``.codex-cover.jpg`` files before the cover predicate could
        # claim them, breaking custom folder covers.
        (_TEST_LIB_ROOT / "comic.cbz").touch()
        (_TEST_LIB_ROOT / ".codex-cover.jpg").touch()
        snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"), covers_only=False)
        names = {Path(p).name for p in snap.paths}
        assert ".codex-cover.jpg" in names


class TestCodexWatchFilter:
    """The watchfiles filter rejects hidden-tree events before classification."""

    def _filter(self, *, covers_only: bool = False) -> CodexWatchFilter:
        lib_root = str(_TEST_LIB_ROOT)
        covers = {lib_root} if covers_only else set()
        return CodexWatchFilter(library_paths={lib_root}, covers_only_paths=covers)

    def test_unrelated_path_rejected(self) -> None:
        assert self._filter()(Change.modified, "/somewhere/else/comic.cbz") is False

    def test_comic_passes(self) -> None:
        assert self._filter()(Change.modified, f"{_TEST_LIB_ROOT}/comic.cbz") is True

    def test_dotfile_basename_rejected(self) -> None:
        assert self._filter()(Change.modified, f"{_TEST_LIB_ROOT}/.DS_Store") is False

    def test_dotfile_ancestor_rejected(self) -> None:
        assert self._filter()(Change.modified, f"{_TEST_LIB_ROOT}/.git/HEAD") is False

    def test_deleted_dotfile_rejected(self) -> None:
        # Deletes used to fall through unconditionally; the dotfile
        # check now blocks them on the path string alone (no disk
        # inspection needed).
        assert self._filter()(Change.deleted, f"{_TEST_LIB_ROOT}/.git/HEAD") is False

    def test_deleted_comic_passes(self) -> None:
        assert self._filter()(Change.deleted, f"{_TEST_LIB_ROOT}/gone.cbz") is True

    def test_folder_cover_dotfile_passes(self) -> None:
        # Regression: ``.codex-cover.jpg`` is a dotfile by name but a
        # legitimate folder cover. Both modify and delete events must
        # reach the importer.
        path = f"{_TEST_LIB_ROOT}/series/.codex-cover.jpg"
        assert self._filter()(Change.modified, path) is True
        assert self._filter()(Change.deleted, path) is True


class TestExpandDirAddedSkipsDotfiles:
    """``os.walk`` recursion under a new dir must prune hidden subtrees."""

    @pytest.fixture(autouse=True)
    def _tmp_library(self):
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)
        _TEST_LIB_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)

    def test_only_visible_comics_emit_events(self) -> None:
        sub = _TEST_LIB_ROOT / "new"
        sub.mkdir()
        (sub / "comic.cbz").touch()
        (sub / ".DS_Store").touch()
        dot_dir = sub / ".git"
        dot_dir.mkdir()
        (dot_dir / "HEAD").touch()
        (dot_dir / "objects").mkdir()
        (dot_dir / "objects" / "abc.cbz").touch()  # Disguised file; still hidden.

        batch = ChangeBatch()
        expand_dir_added(str(sub), library_pk=1, batch=batch, covers_only=False)
        paths = {event.src_path for _pk, event in batch.added}
        assert paths == {str(sub / "comic.cbz")}

    def test_folder_cover_dotfile_emits_event(self) -> None:
        # Regression: ``expand_dir_added`` walks a freshly-added tree
        # and used to skip ``.codex-cover.jpg`` via the dotfile filter
        # before the cover classifier could see it.
        sub = _TEST_LIB_ROOT / "new"
        sub.mkdir()
        (sub / "comic.cbz").touch()
        (sub / ".codex-cover.jpg").touch()

        batch = ChangeBatch()
        expand_dir_added(str(sub), library_pk=1, batch=batch, covers_only=False)
        paths = {event.src_path for _pk, event in batch.added}
        assert str(sub / ".codex-cover.jpg") in paths
        assert str(sub / "comic.cbz") in paths

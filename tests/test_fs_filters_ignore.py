"""Ignore-pattern filtering across the librarian's fs walker, watcher, and helpers."""

from __future__ import annotations

import os
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

    def test_dotfile_basename_with_image_ext_still_ignored(self) -> None:
        # In-library folder covers (``.codex-cover.jpg``) are no longer
        # honored — every dotfile, image-suffix or not, is filtered as
        # OS noise.
        assert is_ignored_path(Path("/lib/comics/series/.codex-cover.jpg")) is True
        assert is_ignored_basename(".codex-cover.jpg") is True
        assert is_ignored_basename(".codex-cover.webp") is True
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

    def test_os_metadata_basenames_registered_by_default(self) -> None:
        # NAS / OS junk trees are ignored out of the box so they are
        # neither imported nor descended into (issue #795).
        for name in ("@eaDir", "#recycle", "__MACOSX", "Thumbs.db", "desktop.ini"):
            assert is_ignored_basename(name) is True


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
        snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"))
        names = {Path(p).name for p in snap.paths}
        assert "comic.cbz" in names
        assert ".DS_Store" not in names

    def test_dotfile_directory_pruned(self) -> None:
        (_TEST_LIB_ROOT / "comic.cbz").touch()
        dot_dir = _TEST_LIB_ROOT / ".git"
        dot_dir.mkdir()
        (dot_dir / "HEAD").touch()
        (dot_dir / "config").touch()
        snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"))
        # Neither the dot-dir nor any descendant should appear.
        assert not any(".git" in Path(p).parts for p in snap.paths)

    def test_folder_cover_dotfile_skipped(self) -> None:
        # Custom folder covers are no longer surfaced from inside
        # library trees — the dotfile filter rejects them like any
        # other hidden file.
        (_TEST_LIB_ROOT / "comic.cbz").touch()
        (_TEST_LIB_ROOT / ".codex-cover.jpg").touch()
        snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"))
        names = {Path(p).name for p in snap.paths}
        assert ".codex-cover.jpg" not in names

    def test_recycle_bin_directory_pruned(self) -> None:
        # Synology recycle bins are registered noise: the walker must
        # never descend into them, so their permission-restricted
        # contents are never scanned (issue #795).
        (_TEST_LIB_ROOT / "comic.cbz").touch()
        recycle = _TEST_LIB_ROOT / "#recycle"
        recycle.mkdir()
        (recycle / "deleted.cbz").touch()
        snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"))
        assert not any("#recycle" in Path(p).parts for p in snap.paths)


class TestDiskSnapshotSurvivesUnreadableDir:
    """A single permission-denied directory must not abort the whole walk."""

    @pytest.fixture(autouse=True)
    def _tmp_library(self):
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)
        _TEST_LIB_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)

    def test_unreadable_subdir_skipped_siblings_survive(self) -> None:
        # Reproduces issue #795: a subdirectory that raises
        # PermissionError on scandir (e.g. a NAS recycle bin) used to
        # crash the poller thread and abort the entire scan. It must now
        # be skipped while every other folder still gets walked. Mock
        # scandir so the test holds regardless of the runner's uid
        # (CI runs as root, where a 0o000 dir stays readable).
        (_TEST_LIB_ROOT / "comic.cbz").touch()
        locked = _TEST_LIB_ROOT / "locked"
        locked.mkdir()
        (locked / "hidden.cbz").touch()

        real_scandir = os.scandir

        def fake_scandir(path):
            if Path(path) == locked:
                raise PermissionError(13, "Permission denied")
            return real_scandir(path)

        with patch.object(os, "scandir", side_effect=fake_scandir):
            snap = DiskSnapshot(str(_TEST_LIB_ROOT), getLogger("test"))

        names = {Path(p).name for p in snap.paths}
        # The sibling comic is still surfaced despite the locked dir.
        assert "comic.cbz" in names
        # The locked directory stat'd fine so its own entry is recorded,
        # but its unreadable contents are not.
        assert "hidden.cbz" not in names
        # And the walk admits it skipped them, so the diff can withhold
        # the deletes they would otherwise imply.
        assert snap.unreadable == {str(locked)}


class TestCodexWatchFilter:
    """The watchfiles filter rejects hidden-tree events before classification."""

    def _filter(self) -> CodexWatchFilter:
        lib_root = str(_TEST_LIB_ROOT)
        return CodexWatchFilter(library_paths={lib_root})

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

    def test_folder_cover_dotfile_rejected(self) -> None:
        # Custom folder covers are no longer discovered via in-library
        # dotfiles — every dotfile reaches the filter and is dropped.
        path = f"{_TEST_LIB_ROOT}/series/.codex-cover.jpg"
        assert self._filter()(Change.modified, path) is False
        assert self._filter()(Change.deleted, path) is False


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
        expand_dir_added(str(sub), library_pk=1, batch=batch)
        paths = {event.src_path for _pk, event in batch.added}
        assert paths == {str(sub / "comic.cbz")}

    def test_folder_cover_dotfile_skipped(self) -> None:
        # Custom folder covers are no longer discovered in-library;
        # the dotfile filter drops them with all other hidden files.
        sub = _TEST_LIB_ROOT / "new"
        sub.mkdir()
        (sub / "comic.cbz").touch()
        (sub / ".codex-cover.jpg").touch()

        batch = ChangeBatch()
        expand_dir_added(str(sub), library_pk=1, batch=batch)
        paths = {event.src_path for _pk, event in batch.added}
        assert paths == {str(sub / "comic.cbz")}

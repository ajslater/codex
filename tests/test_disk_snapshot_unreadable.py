"""
A walk that could not read a path must say so instead of dropping it.

The poller infers deletes by subtracting the disk walk from the database.
Anything the walk skipped silently therefore reads as deleted, and deleting
a comic row cascades the user's bookmarks away for a file that is fine. Two
routes skip a path: ``scandir`` failing on a directory (its children go
missing) and an entry failing to ``stat`` while its parent is listed (the
entry itself and everything under it go missing). The second one used to log
nothing at all.

Failures are mocked rather than made with ``chmod``: CI runs as root, where
mode bits are ignored and a 0o000 directory stays readable, so a
permissions-based test would pass without exercising anything. A 0o000
directory also still stats from its parent, so it can only ever reproduce
the first route.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Final, Self
from unittest.mock import MagicMock, patch

import pytest

from codex.librarian.fs.poller.snapshot import DiskSnapshot

_TEST_LIB_ROOT: Final = Path("/tmp/codex.tests.snapshot_unreadable")  # noqa: S108
_EACCES: Final = PermissionError(13, "Permission denied")
_ENOENT: Final = FileNotFoundError(2, "No such file or directory")
#: The publisher directory each test makes unreadable.
_LOCKED: Final = _TEST_LIB_ROOT / "Publisher"


class _FakeEntry:
    """A scandir entry that refuses to stat, as an unreachable mount's does."""

    def __init__(self, path: Path, error: OSError) -> None:
        self.path = str(path)
        self.name = path.name
        self._error = error

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:  # noqa: ARG002
        """Answer as a directory; only the stat fails."""
        return True

    def stat(self, *, follow_symlinks: bool = True) -> Any:  # noqa: ARG002
        """Raise the way the filesystem did."""
        raise self._error


class _FakeScandir:
    """``os.scandir``'s shape: a context-managed iterator of entries."""

    def __init__(self, entries: list[Any]) -> None:
        self._entries = entries

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def __iter__(self):
        return iter(self._entries)


def _scandir_swapping(target: Path, error: OSError):
    """Return a scandir that hands back an unstattable entry for target."""
    real_scandir = os.scandir

    def fake_scandir(path):
        entries: list[Any] = []
        with real_scandir(path) as scan:
            for entry in scan:
                if Path(entry.path) == target:
                    entries.append(_FakeEntry(target, error))
                else:
                    entries.append(entry)
        return _FakeScandir(entries)

    return fake_scandir


class TestDiskSnapshotUnreadable:
    """``DiskSnapshot`` records what it could not read."""

    @pytest.fixture(autouse=True)
    def _tmp_library(self):
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)
        _TEST_LIB_ROOT.mkdir(parents=True)
        (_TEST_LIB_ROOT / "sibling.cbz").touch()
        _LOCKED.mkdir()
        (_LOCKED / "hidden.cbz").touch()
        yield
        shutil.rmtree(_TEST_LIB_ROOT, ignore_errors=True)

    def _snapshot(self, scandir) -> tuple[DiskSnapshot, MagicMock]:
        log = MagicMock()
        with patch.object(os, "scandir", side_effect=scandir):
            snap = DiskSnapshot(str(_TEST_LIB_ROOT), log)
        return snap, log

    def test_unstattable_directory_hides_itself_and_its_subtree(self) -> None:
        """The silent route: the entry's own stat fails while its parent lists it."""
        snap, _log = self._snapshot(_scandir_swapping(_LOCKED, _EACCES))

        # Both the directory and its contents are missing from the walk,
        # which is exactly why the diff must not treat them as deleted.
        assert str(_LOCKED) not in snap.paths
        assert str(_LOCKED / "hidden.cbz") not in snap.paths
        assert snap.unreadable == {str(_LOCKED)}
        # The sibling still walked: one bad entry is not a failed poll.
        assert str(_TEST_LIB_ROOT / "sibling.cbz") in snap.paths

    def test_unstattable_entry_is_logged(self) -> None:
        """The branch that logged nothing at all is why nobody saw the bug."""
        _snap, log = self._snapshot(_scandir_swapping(_LOCKED, _EACCES))

        log.debug.assert_called()
        assert any("Publisher" in call.args[0] for call in log.debug.call_args_list), (
            log.debug.call_args_list
        )
        # One summary line per walk, however many entries failed.
        log.warning.assert_called_once()
        assert "could not be read" in log.warning.call_args[0][0]

    def test_vanished_entry_is_not_unreadable(self) -> None:
        """A dangling symlink or a mid-scan delete really is gone."""
        snap, log = self._snapshot(_scandir_swapping(_LOCKED, _ENOENT))

        assert str(_LOCKED) not in snap.paths
        assert not snap.unreadable
        log.warning.assert_not_called()

    def test_unreadable_directory_records_its_root(self) -> None:
        """The scandir route: the directory stats, its children never list."""
        real_scandir = os.scandir

        def fake_scandir(path):
            if Path(path) == _LOCKED:
                raise _EACCES
            return real_scandir(path)

        snap, log = self._snapshot(fake_scandir)

        # The directory itself stat'd from its parent, so it is present;
        # only the children it never listed are missing.
        assert str(_LOCKED) in snap.paths
        assert str(_LOCKED / "hidden.cbz") not in snap.paths
        assert snap.unreadable == {str(_LOCKED)}
        log.warning.assert_called()

    def test_clean_walk_records_nothing(self) -> None:
        """No failures, no withholding, no noise."""
        snap, log = self._snapshot(os.scandir)

        assert str(_LOCKED / "hidden.cbz") in snap.paths
        assert not snap.unreadable
        log.warning.assert_not_called()

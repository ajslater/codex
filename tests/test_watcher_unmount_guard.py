"""
A library that isn't really there must not have its comics deleted.

A dropped network share, an ejected volume, or a docker bind mount that
didn't come up presents as an empty or missing directory, so every comic
under it looks deleted at once. The poller refuses to scan in that state;
the watcher already holds the events, so it has to refuse to act on them.
The delete-phase existence check cannot help — while the mount is gone
the files really are unreachable.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Final, override

from django.test import TestCase
from loguru import logger
from watchfiles import Change

from codex.librarian.fs.mounted import DOCKER_UNMOUNTED_FN, unmounted_reason
from codex.librarian.fs.watcher.watcher import LibraryWatcherThread
from codex.librarian.scribe.importer.tasks import ImportTask

_ROOT: Final = Path("/tmp/codex.tests.unmount")  # noqa: S108
_LIBRARY_PK: Final = 1


def _double(stub: object) -> Any:
    """Pass a test double through a concretely-typed seam."""
    return stub


class _ListQueue:
    """Records what the watcher queues."""

    def __init__(self, items: list) -> None:
        self.items = items

    def put(self, item) -> None:
        self.items.append(item)


def _watcher() -> LibraryWatcherThread:
    """Build a watcher without its threading machinery."""
    watcher = LibraryWatcherThread.__new__(LibraryWatcherThread)
    watcher.log = _double(logger)
    watcher._library_paths = {str(_ROOT): _LIBRARY_PK}  # noqa: SLF001
    return watcher


def _delete_task() -> ImportTask:
    return ImportTask(
        library_id=_LIBRARY_PK,
        files_deleted=frozenset({str(_ROOT / "a.cbz")}),
    )


class UnmountedReasonTests(TestCase):
    """The shared check both scanners consult."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_ROOT, ignore_errors=True)
        _ROOT.mkdir(parents=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_ROOT, ignore_errors=True)

    def test_a_populated_directory_looks_mounted(self) -> None:
        (_ROOT / "a.cbz").write_text("comic")

        assert not unmounted_reason(_ROOT)

    def test_a_missing_directory_is_flagged(self) -> None:
        shutil.rmtree(_ROOT)

        assert "not there" in unmounted_reason(_ROOT)

    def test_an_empty_directory_is_flagged(self) -> None:
        assert "empty" in unmounted_reason(_ROOT)

    def test_the_docker_marker_is_flagged(self) -> None:
        (_ROOT / DOCKER_UNMOUNTED_FN).write_text("")

        assert "docker" in unmounted_reason(_ROOT)


class WatcherUnmountGuardTests(TestCase):
    """Deletes from a vanished library never reach the queue."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_ROOT, ignore_errors=True)
        _ROOT.mkdir(parents=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_ROOT, ignore_errors=True)

    def test_deletes_are_dropped_when_the_library_is_empty(self) -> None:
        """An empty root means the mount is gone, not that every comic is."""
        assert _watcher()._is_a_vanished_library(_delete_task())  # noqa: SLF001

    def test_deletes_are_dropped_when_the_root_is_missing(self) -> None:
        shutil.rmtree(_ROOT)

        assert _watcher()._is_a_vanished_library(_delete_task())  # noqa: SLF001

    def test_real_deletes_still_pass(self) -> None:
        """A library with other comics still in it is really deleting one."""
        (_ROOT / "b.cbz").write_text("comic")

        assert not _watcher()._is_a_vanished_library(_delete_task())  # noqa: SLF001

    def test_a_task_without_deletes_is_never_blocked(self) -> None:
        """Adds and modifies can't destroy anything, so they are not checked."""
        task = ImportTask(
            library_id=_LIBRARY_PK,
            files_modified=frozenset({str(_ROOT / "a.cbz")}),
        )

        assert not _watcher()._is_a_vanished_library(task)  # noqa: SLF001

    def test_an_unknown_library_is_not_blocked(self) -> None:
        """Without a root to check, the guard stays out of the way."""
        task = ImportTask(
            library_id=999, files_deleted=frozenset({str(_ROOT / "a.cbz")})
        )

        assert not _watcher()._is_a_vanished_library(task)  # noqa: SLF001


class WatcherProcessChangesTests(TestCase):
    """The guard is wired into the path that queues the work."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_ROOT, ignore_errors=True)
        _ROOT.mkdir(parents=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_ROOT, ignore_errors=True)

    @staticmethod
    def _run(queue: list) -> None:
        watcher = _watcher()
        watcher.librarian_queue = _double(_ListQueue(queue))
        watcher._process_changes(  # noqa: SLF001
            {(Change.deleted, str(_ROOT / "a.cbz"))}
        )

    def test_an_empty_library_queues_nothing(self) -> None:
        """The whole library looking deleted never reaches the importer."""
        queued: list = []

        self._run(queued)

        assert not queued

    def test_a_populated_library_queues_the_delete(self) -> None:
        """A real delete is still reported."""
        (_ROOT / "b.cbz").write_text("comic")
        queued: list = []

        self._run(queued)

        assert len(queued) == 1
        assert queued[0].files_deleted == {str(_ROOT / "a.cbz")}

"""Watcher Tasks."""

from dataclasses import dataclass

from codex.librarian.tasks import LibrarianTask
from codex.librarian.watcher.events import PollEvent, WatchEvent


@dataclass
class WatcherTask(LibrarianTask):
    """Watcher tasks."""


@dataclass
class WatcherPollLibrariesTask(WatcherTask):
    """Tell poller to poll these libraries now."""

    library_ids: frozenset
    force: bool


@dataclass
class WatcherEventTask(WatcherTask):
    """Task for filesystem events."""

    library_id: int
    event: WatchEvent | PollEvent


@dataclass
class WatcherSyncTask(WatcherTask):
    """Sync watches with libraries."""

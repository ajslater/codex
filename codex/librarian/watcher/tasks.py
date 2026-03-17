"""Watcher Tasks."""

from dataclasses import dataclass

from codex.librarian.tasks import LibrarianTask
from codex.librarian.watcher.events import WatchEvent
from codex.librarian.watcher.poller.events import PollEvent


@dataclass
class WatcherTask(LibrarianTask):
    """Watcher tasks."""


@dataclass
class WatcherEventTask(WatcherTask):
    """Task for filesystem events."""

    library_id: int
    event: WatchEvent | PollEvent


@dataclass
class WatcherSyncTask(WatcherTask):
    """Sync watches with libraries."""

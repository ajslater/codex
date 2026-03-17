"""Watchdog Tasks."""

from dataclasses import dataclass

from codex.librarian.tasks import LibrarianTask
from codex.librarian.watchdog.events import PollEvent, WatchEvent


@dataclass
class WatchdogTask(LibrarianTask):
    """Watchdog tasks."""


@dataclass
class WatchdogPollLibrariesTask(WatchdogTask):
    """Tell poller to poll these libraries now."""

    library_ids: frozenset
    force: bool


@dataclass
class WatchdogEventTask(WatchdogTask):
    """Task for filesystem events."""

    library_id: int
    event: WatchEvent | PollEvent


@dataclass
class WatchdogSyncTask(WatchdogTask):
    """Sync watches with libraries."""

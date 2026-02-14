"""Watchdog Tasks."""

from dataclasses import dataclass

from watchdog.events import FileSystemEvent

from codex.librarian.tasks import LibrarianTask


@dataclass
class WatchdogTask(LibrarianTask):
    """Watchdog tasks."""


@dataclass
class WatchdogPollLibrariesTask(WatchdogTask):
    """Tell observer to poll these libraries now."""

    library_ids: frozenset
    force: bool


@dataclass
class WatchdogEventTask(WatchdogTask):
    """Task for filesystem events."""

    library_id: int
    event: FileSystemEvent


@dataclass
class WatchdogSyncTask(WatchdogTask):
    """Sync watches with libraries."""

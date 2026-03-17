"""Poller Tasks."""

from dataclasses import dataclass

from codex.librarian.watcher.tasks import WatcherTask


@dataclass
class WatcherPollLibrariesTask(WatcherTask):
    """Tell poller to poll these libraries now."""

    library_ids: frozenset
    force: bool

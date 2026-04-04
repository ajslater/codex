"""Restart Watcher to sync with database."""

from dataclasses import dataclass

from codex.librarian.fs.tasks import FSTask


@dataclass
class FSWatcherRestartTask(FSTask):
    """Restart the Watcher."""

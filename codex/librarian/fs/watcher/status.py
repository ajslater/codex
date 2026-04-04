"""Watcher Statii."""

from codex.librarian.fs.status import FSStatus


class FSWatcherRestartStatus(FSStatus):
    """FS Watcher Restart Status."""

    CODE = "WRS"
    VERB = "Restart"
    _verbed = "Restarted"
    ITEM_NAME = "file watcher"
    SINGLE = True
    log_success = True


WATCHER_STATII = (FSWatcherRestartStatus,)

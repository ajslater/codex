"""Watcher Statii."""

from abc import ABC

from codex.librarian.status import Status


class WatcherStatus(Status, ABC):
    """Watcher Statii."""


class WatcherPollStatus(WatcherStatus):
    """Watcher Poll Status."""

    CODE = "WPO"
    VERB = "Poll"
    _verbed = "Polled"
    ITEM_NAME = "library"
    SINGLE = True


WATCHER_STATII = (WatcherPollStatus,)

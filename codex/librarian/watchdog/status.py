"""Watchdog Statii."""

from abc import ABC

from codex.librarian.status import Status


class WatchdogStatus(Status, ABC):
    """Watchdog Statii."""


class WatchdogPollStatus(WatchdogStatus):
    """Watchdog Poll Status."""

    CODE = "WPO"
    VERB = "Poll"
    _verbed = "Polled"
    ITEM_NAME = "library"
    SINGLE = True


WATCHDOG_STATII = (WatchdogPollStatus,)

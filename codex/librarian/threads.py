"""Abstract Thread worker for doing queued tasks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from queue import Empty, SimpleQueue
from threading import Thread
from time import monotonic
from typing import TYPE_CHECKING, override

from django.db import close_old_connections
from setproctitle import setproctitle

from codex.librarian.worker import WorkerStatusMixin

if TYPE_CHECKING:
    # Both type-hint-only — defer until type checkers run. Keeps
    # the runtime import graph for ``threads.py`` lean across the
    # nine librarian modules that import it.
    from multiprocessing.queues import Queue

    from loguru._logger import Logger


class BreakLoopError(Exception):
    """Simple way to break out of function nested loop."""


class NamedThread(Thread, WorkerStatusMixin, ABC):
    """A thread that sets its name for ps."""

    SHUTDOWN_MSG: str | tuple = "shutdown"
    SHUTDOWN_TIMEOUT = 5

    def __init__(
        self,
        logger_: Logger,
        librarian_queue: Queue,
        db_write_lock,
        name="",
        **kwargs,
    ) -> None:
        """Initialize queues."""
        self.init_worker(logger_, librarian_queue, db_write_lock)
        if not name:
            name = self.__class__.__name__
        super().__init__(name=name, **kwargs)

    def run_start(self) -> None:
        """First thing to do when running a new thread."""
        self.log.debug(f"Started {self.name}")
        setproctitle(self.name)

    @override
    def join(self, timeout=None) -> None:
        """End the thread."""
        self.log.debug(f"Waiting for {self.__class__.__name__} to join.")
        super().join(self.SHUTDOWN_TIMEOUT)
        self.log.debug(f"{self.__class__.__name__} joined.")

    def stop(self):
        """Noop."""
        self.log.debug(f"Stop Requested {self.__class__.__name__}")


class QueuedThread(NamedThread, ABC):
    """Abstract Thread worker for doing queued tasks."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize with overridden name and as a daemon thread."""
        self.queue = kwargs.pop("queue", SimpleQueue())
        super().__init__(*args, daemon=True, **kwargs)

    @abstractmethod
    def process_item(self, item):
        """Process one item from the queue."""
        raise NotImplementedError

    def get_timeout(self) -> float | None:
        """Set no timeout by default."""
        return

    def timed_out(self):
        """Override to things on queue timeout."""

    def _check_item(self) -> None:
        """Get items, with timeout. Check for shutdown and Empty."""
        timeout = self.get_timeout()
        try:
            item = self.queue.get(timeout=timeout)
            if item == self.SHUTDOWN_MSG:
                raise BreakLoopError
            self.process_item(item)
        except Empty:
            self.timed_out()

    @override
    def run(self) -> None:
        """Run thread loop."""
        self.run_start()
        while True:
            try:
                close_old_connections()
                self._check_item()
            except BreakLoopError:
                break
            except Exception:
                self.log.exception(f"{self.__class__.__name__} crashed:")
        self.log.debug(f"Stopped {self.__class__.__name__}")

    @override
    def stop(self) -> None:
        """Stop the thread."""
        super().stop()
        self.queue.put(self.SHUTDOWN_MSG)


class AggregateMessageQueuedThread(QueuedThread, ABC):
    """Abstract Thread worker for buffering and aggregating messages."""

    FLOOD_DELAY = 1.0
    MAX_DELAY = 5.0

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the cache."""
        self.cache = {}
        # ``time.monotonic`` over ``time.time``: elapsed-time math
        # (``monotonic() - self._last_send``) must not be affected by
        # wall-clock jumps from NTP / daylight saving / manual
        # adjustments. Slightly cheaper than ``time.time`` on most
        # platforms (clock_gettime(CLOCK_MONOTONIC) vs gettimeofday)
        # — the bigger win is correctness on the flush-timing path
        # in subclasses like BookmarkThread / NotifierThread.
        self._last_send = monotonic()
        super().__init__(*args, **kwargs)

    def set_last_send(self) -> None:
        """Set the last send time to now."""
        self._last_send = monotonic()

    @override
    def get_timeout(self):
        """Aggregate queue has a conditional timeout."""
        return self.FLOOD_DELAY if self.cache else None

    @abstractmethod
    def aggregate_items(self, item):
        """Abstract method for aggregating items."""
        raise NotImplementedError

    @abstractmethod
    def send_all_items(self):
        """Abstract method for sending all items."""
        raise NotImplementedError

    def cleanup_cache(self, keys) -> None:
        """Remove sent messages from the cache and record send times."""
        for key in keys:
            self.cache.pop(key, None)
        self.set_last_send()

    @override
    def process_item(self, item) -> None:
        """Aggregate items and sleep in case there are more."""
        self.aggregate_items(item)
        since_last_timed_out = monotonic() - self._last_send
        waited_too_long = since_last_timed_out > self.MAX_DELAY
        if waited_too_long:
            self.timed_out()

    @override
    def timed_out(self) -> None:
        """Send the items and set when we did this."""
        self.send_all_items()
        self.set_last_send()

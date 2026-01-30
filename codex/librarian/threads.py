"""Abstract Thread worker for doing queued tasks."""

import time
from abc import ABC, abstractmethod
from multiprocessing.queues import Queue
from queue import Empty, SimpleQueue
from threading import Thread

from django.db import close_old_connections
from loguru._logger import Logger
from typing_extensions import override

from codex.librarian.worker import WorkerStatusMixin


class BreakLoopError(Exception):
    """Simple way to break out of function nested loop."""


class NamedThread(Thread, WorkerStatusMixin, ABC):
    """A thread that sets its name for ps."""

    def __init__(
        self,
        logger_: Logger,
        librarian_queue: Queue,
        db_write_lock,
        name="",
        **kwargs,
    ):
        """Initialize queues."""
        self.init_worker(logger_, librarian_queue, db_write_lock)
        if not name:
            name = self.__class__.__name__
        super().__init__(name=name, **kwargs)

    def run_start(self):
        """First thing to do when running a new thread."""
        self.log.debug(f"Started {self.name}")


class QueuedThread(NamedThread, ABC):
    """Abstract Thread worker for doing queued tasks."""

    SHUTDOWN_MSG: str | tuple = "shutdown"
    SHUTDOWN_TIMEOUT = 5

    def __init__(self, *args, **kwargs):
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

    def _check_item(self):
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
    def run(self):
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

    def stop(self):
        """Stop the thread."""
        self.queue.put(self.SHUTDOWN_MSG)

    @override
    def join(self, timeout=None):
        """End the thread."""
        self.log.debug(f"Waiting for {self.__class__.__name__} to join.")
        super().join(self.SHUTDOWN_TIMEOUT)
        self.log.debug(f"{self.__class__.__name__} joined.")


class AggregateMessageQueuedThread(QueuedThread, ABC):
    """Abstract Thread worker for buffering and aggregating messages."""

    FLOOD_DELAY = 1.0
    MAX_DELAY = 5.0

    def __init__(self, *args, **kwargs):
        """Initialize the cache."""
        self.cache = {}
        self._last_send = time.time()
        super().__init__(*args, **kwargs)

    def set_last_send(self):
        """Set the last send time to now."""
        self._last_send = time.time()

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

    def cleanup_cache(self, keys):
        """Remove sent messages from the cache and record send times."""
        for key in keys:
            self.cache.pop(key, None)
        self.set_last_send()

    @override
    def process_item(self, item):
        """Aggregate items and sleep in case there are more."""
        self.aggregate_items(item)
        since_last_timed_out = time.time() - self._last_send
        waited_too_long = since_last_timed_out > self.MAX_DELAY
        if waited_too_long:
            self.timed_out()

    @override
    def timed_out(self):
        """Send the items and set when we did this."""
        self.send_all_items()
        self.set_last_send()

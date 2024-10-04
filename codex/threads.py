"""Abstract Thread worker for doing queued tasks."""

import time
from abc import ABC, abstractmethod
from queue import Empty, SimpleQueue
from threading import Thread

from codex.worker_base import WorkerBaseMixin


class BreakLoopError(Exception):
    """Simple way to break out of function nested loop."""


class NamedThread(Thread, WorkerBaseMixin, ABC):
    """A thread that sets its name for ps."""

    def __init__(self, *args, **kwargs):
        """Initialize queues."""
        librarian_queue = kwargs.pop("librarian_queue")
        log_queue = kwargs.pop("log_queue")
        self.init_worker(log_queue, librarian_queue)
        super().__init__(*args, **kwargs)

    def run_start(self):
        """First thing to do when running a new thread."""
        self.log.debug(f"Started {self.__class__.__name__}")


class QueuedThread(NamedThread, ABC):
    """Abstract Thread worker for doing queued tasks."""

    SHUTDOWN_MSG = "shutdown"
    SHUTDOWN_TIMEOUT = 5

    def __init__(self, *args, **kwargs):
        """Initialize with overridden name and as a daemon thread."""
        self.queue = kwargs.pop("queue", SimpleQueue())
        super().__init__(*args, name=self.__class__.__name__, daemon=True, **kwargs)

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
                raise BreakLoopError  # TRY301
            self.process_item(item)
        except Empty:
            self.timed_out()

    def run(self):
        """Run thread loop."""
        self.run_start()
        while True:
            try:
                self._check_item()
            except BreakLoopError:
                break
            except Exception:
                self.log.exception(f"{self.__class__.__name__} crashed:")
        self.log.debug(f"Stopped {self.__class__.__name__}")

    def stop(self):
        """Stop the thread."""
        self.queue.put(self.SHUTDOWN_MSG)

    def join(self, timeout=None):  # noqa: ARG002
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
        self._last_timed_out = time.time()
        super().__init__(*args, **kwargs)

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
        self._last_send = time.time()

    def process_item(self, item):
        """Aggregate items and sleep in case there are more."""
        self.aggregate_items(item)
        since_last_timed_out = time.time() - self._last_timed_out
        waited_too_long = since_last_timed_out > self.MAX_DELAY
        if waited_too_long:
            self.timed_out()

    def timed_out(self):
        """Send the items and set when we did this."""
        self.send_all_items()
        self._last_timed_out = time.time()

"""Abstract Thread worker for doing queued tasks."""
import time

from abc import ABC, abstractmethod
from multiprocessing import Queue
from queue import Empty
from threading import Thread

from codex.logger_base import LoggerBase


class BreakLoopError(Exception):
    """Simple way to break out of function nested loop."""

    pass


class NamedThread(Thread, LoggerBase, ABC):
    """A thread that sets its name for ps."""

    def __init__(self, *args, **kwargs):
        """Initialize queues."""
        self.librarian_queue = kwargs.pop("librarian_queue", None)
        log_queue = kwargs.pop("log_queue")
        self.init_logger(log_queue)
        super().__init__(*args, **kwargs)

    @property
    @classmethod
    @abstractmethod
    def NAME(cls):  # noqa: N802
        """Name the thread."""
        raise NotImplementedError()

    def run_start(self):
        """First thing to do when running a new thread."""
        self.logger.info(f"Started {self.NAME} thread")


class QueuedThread(NamedThread, ABC):
    """Abstract Thread worker for doing queued tasks."""

    SHUTDOWN_MSG = "shutdown"
    SHUTDOWN_TIMEOUT = 5

    def __init__(self, *args, **kwargs):
        """Initialize with overridden name and as a daemon thread."""
        self.queue = kwargs.pop("queue", Queue())
        super().__init__(*args, name=self.NAME, daemon=True, **kwargs)

    @abstractmethod
    def process_item(self, item):
        """Process one item from the queue."""
        raise NotImplementedError()

    def get_timeout(self):
        """Set no timeout by default."""
        return None

    def timed_out(self):
        """Override to things on queue timeout."""
        pass

    def _check_item(self):
        """Get items, with timeout. Check for shutdown and Empty."""
        timeout = self.get_timeout()
        try:
            item = self.queue.get(timeout=timeout)
            if item == self.SHUTDOWN_MSG:
                raise BreakLoopError()
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
            except Exception as exc:
                self.logger.error(f"{self.NAME} crashed:")
                self.logger.exception(exc)
        self.logger.info(f"Stopped {self.NAME} thread")

    def stop(self):
        """Stop the thread."""
        self.queue.put(self.SHUTDOWN_MSG)

    def join(self):
        """End the thread."""
        self.logger.debug(f"Waiting for {self.NAME} to join.")
        super().join(self.SHUTDOWN_TIMEOUT)
        self.logger.debug(f"{self.NAME} joined.")


class AggregateMessageQueuedThread(QueuedThread, ABC):
    """Abstract Thread worker for buffering and aggregating messages."""

    FLOOD_DELAY = 1
    MAX_DELAY = 5

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
        raise NotImplementedError()

    @abstractmethod
    def send_all_items(self):
        """Abstract method for sending all items."""
        raise NotImplementedError()

    def cleanup_cache(self, keys):
        """Remove sent messages from the cache and record send times."""
        for key in keys:
            del self.cache[key]
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

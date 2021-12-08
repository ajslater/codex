"""Abstract Thread worker for doing queued tasks."""
import time

from abc import ABC, abstractmethod
from logging import getLogger
from multiprocessing import Queue
from queue import Empty
from threading import Thread


LOG = getLogger(__name__)


class BreakLoopError(Exception):
    """Simple way to break out of function nested loop."""

    pass


class QueuedThread(Thread, ABC):
    """Abstract Thread worker for doing queued tasks."""

    SHUTDOWN_MSG = "shutdown"
    SHUTDOWN_TIMEOUT = 5

    NAME = "abstract-queued-thread"

    def __init__(self):
        """Initialize with overridden name and as a daemon thread."""
        self.queue = Queue()
        super().__init__(name=self.NAME, daemon=True)

    @abstractmethod
    def _process_item(self, item):
        """Process one item from the queue."""
        raise NotImplementedError()

    def _get_timeout(self):
        """Set no timeout by default."""
        return None

    def _timed_out(self):
        """Override to things on queue timeout."""
        pass

    def _check_item(self):
        """Get items, with timeout. Check for shutdown and Empty."""
        timeout = self._get_timeout()
        try:
            item = self.queue.get(timeout=timeout)
            if item == self.SHUTDOWN_MSG:
                raise BreakLoopError()
            self._process_item(item)
        except Empty:
            self._timed_out()

    def run(self):
        """Run thread loop."""
        LOG.verbose(f"Started {self.NAME} thread")  # type: ignore
        while True:
            try:
                self._check_item()
            except BreakLoopError:
                break
            except Exception as exc:
                LOG.exception(exc)
        LOG.verbose(f"Stopped {self.NAME} thread")  # type: ignore

    def stop(self):
        """Stop the thread."""
        self.queue.put(self.SHUTDOWN_MSG)

    def join(self):
        """End the thread."""
        super().join(self.SHUTDOWN_TIMEOUT)


class AggregateMessageQueuedThread(QueuedThread, ABC):
    """Abstract Thread worker for buffering and aggregating messages."""

    FLOOD_DELAY = 2
    MAX_DELAY = 15

    def __init__(self, *args, **kwargs):
        """Initialize the cache."""
        self.cache = {}
        self._last_timed_out = time.time()
        super().__init__(*args, **kwargs)

    def _get_timeout(self):
        """Aggregate queue has a conditional timeout."""
        return self.FLOOD_DELAY if self.cache else None

    @abstractmethod
    def _aggregate_items(self, item):
        """Abstract method for aggregating items."""
        raise NotImplementedError()

    @abstractmethod
    def _send_all_items(self):
        """Abstract method for sending all items."""
        raise NotImplementedError()

    def _cleanup_cache(self, keys):
        """Remove sent messages from the cache and record send times."""
        for key in keys:
            del self.cache[key]
        self._last_send = time.time()

    def _process_item(self, item):
        """Aggregate items and sleep in case there are more."""
        self._aggregate_items(item)
        since_last_timed_out = time.time() - self._last_timed_out
        waited_too_long = since_last_timed_out > self.MAX_DELAY
        if waited_too_long:
            self._timed_out()

    def _timed_out(self):
        """Send the items and set when we did this."""
        self._send_all_items()
        self._last_timed_out = time.time()

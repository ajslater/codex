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

    def _check_item(self):
        """Get items, with timoeout. Check for shutdown and Empty."""
        timeout = self._get_timeout()
        try:
            item = self.queue.get(timeout=timeout)
            if item == self.SHUTDOWN_MSG:
                raise BreakLoopError()
            self._process_item(item)
        except Empty:
            pass

    def _post_process_hook(self):
        """Overidable post processing hook."""
        pass

    def run(self):
        """Run thread loop."""
        LOG.verbose(f"Started {self.NAME} thread")  # type: ignore
        while True:
            try:
                self._check_item()
                self._post_process_hook()
            except BreakLoopError:
                break
            except Exception as exc:
                LOG.exception(exc)
        LOG.verbose(f"Stopped {self.NAME} thread")  # type: ignore

    def join(self):
        """End the thread."""
        self.queue.put(self.SHUTDOWN_MSG)
        super().join(self.SHUTDOWN_TIMEOUT)


class AggregateMessageQueuedThread(QueuedThread, ABC):
    """Abstract Thread worker for buffering and aggregating messages."""

    FLOOD_DELAY = 2
    MAX_DELAY = 30

    def __init__(self, *args, **kwargs):
        """Initialize the cache."""
        self.cache = {}
        self.send_times = {}
        super().__init__(*args, **kwargs)

    @abstractmethod
    def _aggregate_items(self, item):
        """Abstract method for aggregating items."""
        raise NotImplementedError()

    @abstractmethod
    def _send_all_items(self):
        """Abstract method for sending all items."""
        raise NotImplementedError()

    def _do_send_item(self, item):
        """Return whether or not its time to send this item."""
        last_send = self.send_times.get(item, 0)
        waited_enough = time.time() - last_send > self.MAX_DELAY
        return self.queue.empty() or waited_enough

    def _cleanup_cache(self, keys):
        """Remove sent messages from the cache and record send times."""
        for key in keys:
            self.send_times[key] = time.time()
            del self.cache[key]

    def _process_item(self, item):
        """Aggregate items and sleep in case there are more."""
        self._aggregate_items(item)
        if self.queue.empty():
            time.sleep(self.FLOOD_DELAY)

    def _get_timeout(self):
        """Aggregate queue has a conditional timeout."""
        return self.FLOOD_DELAY if self.cache else None

    def _post_process_hook(self):
        """Top of loop processes items, then send items."""
        self._send_all_items()

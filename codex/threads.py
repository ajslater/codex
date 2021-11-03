"""Abstract Thread worker for doing queued tasks."""
import logging
import time

from abc import ABC, abstractmethod
from multiprocessing import Queue
from queue import Empty
from threading import Thread


LOG = logging.getLogger(__name__)


class QueuedThread(Thread):
    """Abstract Thread worker for doing queued tasks."""

    SHUTDOWN_MSG = "shutdown"
    SHUTDOWN_TIMEOUT = 5

    NAME = "abstract-queued-thread"

    def __init__(self):
        """Initialize with overridden name and as a daemon thread."""
        self.queue = Queue()
        super().__init__(name=self.NAME, daemon=True)

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
        for key in keys:
            self.send_times[key] = time.time()
            del self.cache[key]

    def run(self):
        """Run message getting, aggregating and sending loop"""
        LOG.info(f"Started {self.NAME} thread")
        # last_send = time.time()
        while True:
            try:
                # last_block = time.time()
                timeout = self.FLOOD_DELAY if self.cache else None
                try:
                    item = self.queue.get(timeout=timeout)
                    if item == self.SHUTDOWN_MSG:
                        break
                    self._aggregate_items(item)
                    if self.queue.empty():
                        time.sleep(self.FLOOD_DELAY)
                except Empty:
                    pass

                # waited_enough = time.time() - last_send > self.MAX_DELAY
                # if not (self.queue.empty() or waited_enough):
                #    continue
                self._send_all_items()
                # last_send = time.time()
            except Exception as exc:
                LOG.exception(exc)
        LOG.info(f"Stopped {self.NAME} thread")

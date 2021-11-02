"""Abstract Thread worker for doing queued tasks."""
import time

from multiprocessing import Queue
from threading import Thread


class TimedMessage:
    """A message that timestamps its own creation."""

    def __init__(self, *args, **kwargs):
        """Set time of creation."""
        self.time = time.time()
        super().__init__(*args, **kwargs)


class QueuedWorker(Thread):
    """Abstract Thread worker for doing queued tasks."""

    SHUTDOWN_MSG = "shutdown"
    SHUTDOWN_TIMEOUT = 5
    NAME = "abstract-buffer-worker"

    def __init__(self):
        """Initialize with overridden name and as a daemon thread."""
        self.queue = Queue()
        super().__init__(name=self.NAME, daemon=True)

    def join(self):
        """End the thread."""
        self.queue.put(self.SHUTDOWN_MSG)
        super().join(self.SHUTDOWN_TIMEOUT)

"""Abstract Thread worker for doing queued tasks."""
import time

from queue import Queue
from threading import Thread


class TimedMessage:
    """A message that timestamps its own creation."""

    def __init__(self, *args, **kwargs):
        """Set time of creation."""
        self.time = time.time()
        super().__init__(*args, **kwargs)


class BufferThread(Thread):
    """Abstract Thread worker for doing queued tasks."""

    thread = None
    MESSAGE_QUEUE = Queue()
    SHUTDOWN_MSG = "shutdown"
    SHUTDOWN_TIMEOUT = 5
    NAME = "abstract-buffer-worker"

    def __init__(self):
        """Initialize with overridden name and as a daemon thread."""
        super().__init__(name=self.NAME, daemon=True)

    @classmethod
    def startup(cls):
        """Start the thread."""
        cls.thread = cls()
        cls.thread.start()

    @classmethod
    def shutdown(cls):
        """End the thread."""
        cls.MESSAGE_QUEUE.put(cls.SHUTDOWN_MSG)
        if cls.thread:
            cls.thread.join(cls.SHUTDOWN_TIMEOUT)

"""Watch file trees for changes."""
import logging

from threading import Condition
from threading import Thread

from codex.librarian.queue import QUEUE
from codex.librarian.queue import ScannerCronTask
from codex.librarian.queue import UpdateCronTask
from codex.librarian.queue import WatcherCronTask


LOG = logging.getLogger(__name__)


class Crond(Thread):
    """Run a scheduled service for codex."""

    COND = Condition()
    run_thread = True
    WAIT_INTERVAL = 60 * 5  # Run cron every 5 minutes

    def worker(self, cond):
        """Watch a path and log the events."""
        LOG.info("Started cron")
        with cond:
            while self.run_thread:
                QUEUE.put(ScannerCronTask(sleep=0))
                QUEUE.put(WatcherCronTask(sleep=0))
                QUEUE.put(UpdateCronTask(sleep=0, force=False))
                cond.wait(timeout=self.WAIT_INTERVAL)
        LOG.info("Stopped cron.")

    def __init__(self):
        """Intialize this thread with the worker."""
        super().__init__(
            target=self.worker, name="crond", args=(self.COND,), daemon=True
        )

    def stop(self):
        """Stop the cron thread."""
        self.run_thread = False
        with self.COND:
            self.COND.notify()

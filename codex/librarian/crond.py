"""Watch file trees for changes."""
import logging

from threading import Condition, Thread

from codex.librarian.queue import (
    QUEUE,
    ScannerCronTask,
    UpdateCronTask,
    VacuumCronTask,
    WatcherCronTask,
)


LOG = logging.getLogger(__name__)


class Crond(Thread):
    """Run a scheduled service for codex."""

    COND = Condition()
    run_thread = True
    WAIT_INTERVAL = 60 * 5  # Run cron every 5 minutes
    SHUTDOWN_TIMEOUT = 5

    def run(self):
        """Watch a path and log the events."""
        LOG.info("Started cron")
        with self.COND:
            while self.run_thread:
                QUEUE.put(ScannerCronTask(sleep=0))
                QUEUE.put(WatcherCronTask(sleep=0))
                QUEUE.put(UpdateCronTask(sleep=0, force=False))
                QUEUE.put(VacuumCronTask())
                self.COND.wait(timeout=self.WAIT_INTERVAL)
        LOG.info("Stopped cron.")

    def __init__(self):
        """Intialize this thread with the worker."""
        super().__init__(name="crond", daemon=True)

    def stop(self):
        """Stop the cron thread."""
        self.run_thread = False
        with self.COND:
            self.COND.notify()

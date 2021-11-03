"""Watch file trees for changes."""
from logging import getLogger
from threading import Condition, Thread

from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    ScannerCronTask,
    UpdateCronTask,
    VacuumCronTask,
    WatcherCronTask,
)


LOG = getLogger(__name__)


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
                try:
                    LIBRARIAN_QUEUE.put(ScannerCronTask(sleep=0))
                    LIBRARIAN_QUEUE.put(WatcherCronTask(sleep=0))
                    LIBRARIAN_QUEUE.put(UpdateCronTask(sleep=0, force=False))
                    LIBRARIAN_QUEUE.put(VacuumCronTask())
                    self.COND.wait(timeout=self.WAIT_INTERVAL)
                except Exception as exc:
                    LOG.exception(exc)
        LOG.info("Stopped cron.")

    def __init__(self):
        """Intialize this thread with the worker."""
        super().__init__(name="crond", daemon=True)

    def join(self):
        """Stop the cron thread."""
        self.run_thread = False
        with self.COND:
            self.COND.notify()
        super().join()

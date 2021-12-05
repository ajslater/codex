"""Watch file trees for changes."""
from datetime import datetime, time, timedelta
from logging import getLogger
from threading import Condition, Event, Thread
from time import sleep

from humanize import precisedelta

from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BackupCronTask,
    UpdateCronTask,
    VacuumCronTask,
)


LOG = getLogger(__name__)
DEBOUNCE = 5


class Crond(Thread):
    """Run a scheduled service for codex."""

    NAME = "Cron"

    @staticmethod
    def _until_midnight():
        """Get seconds until midnight."""
        now = datetime.now().astimezone()
        tomorrow = (now + timedelta(days=1)).astimezone()
        next_midnight = datetime.combine(tomorrow, time.min).astimezone()
        delta = next_midnight - now
        return max(0, delta.total_seconds())

    def run(self):
        """Watch a path and log the events."""
        LOG.verbose(f"Started {self.NAME} thread.")  # type: ignore
        with self._cond:
            while not self._stop_event.is_set():
                timeout = self._until_midnight()
                LOG.verbose(  # type: ignore
                    f"Waiting {precisedelta(timeout)} until next maintenance."
                )
                self._cond.wait(timeout=timeout)
                try:
                    LIBRARIAN_QUEUE.put(VacuumCronTask())
                    LIBRARIAN_QUEUE.put(BackupCronTask())
                    LIBRARIAN_QUEUE.put(UpdateCronTask(force=False))
                except Exception as exc:
                    LOG.exception(exc)
                # Queing takes less than a second and can run three times.
                sleep(DEBOUNCE)
        LOG.verbose(f"Stopped {self.NAME} thread.")  # type: ignore

    def __init__(self):
        """Initialize this thread with the worker."""
        self._stop_event = Event()
        self._cond = Condition()
        super().__init__(name=self.NAME, daemon=True)

    def stop(self):
        """Stop the cron thread."""
        self._stop_event.set()
        with self._cond:
            self._cond.notify()

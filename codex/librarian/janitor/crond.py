"""Perform maintence tasks."""
from datetime import datetime, time, timedelta
from logging import getLogger
from threading import Condition, Event, Thread
from time import sleep

from django.utils import timezone
from humanize import precisedelta

from codex.librarian.janitor.update import restart_codex, update_codex
from codex.librarian.janitor.vacuum import backup_db, vacuum_db
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BackupTask,
    RestartTask,
    UpdateTask,
    VacuumTask,
)
from codex.settings.settings import CACHE_PATH


LOG = getLogger(__name__)
DEBOUNCE = 5
CRON_TIMESTAMP = CACHE_PATH / "crond_timestamp"
ONE_DAY = timedelta(days=1)


class Crond(Thread):
    """Run a scheduled service for codex."""

    NAME = "Cron"

    @staticmethod
    def _get_timeout():
        """Get seconds until midnight."""
        try:
            mtime = CRON_TIMESTAMP.stat().st_mtime
        except FileNotFoundError:
            mtime = 0

        last_cron = datetime.fromtimestamp(mtime, tz=timezone.utc)
        now = timezone.now()
        if now - last_cron > ONE_DAY:
            # it's been too long
            seconds = 0
        else:
            # wait until next midnight
            tomorrow = (now + ONE_DAY).astimezone()
            next_midnight = datetime.combine(tomorrow, time.min).astimezone()
            delta = next_midnight - now
            seconds = max(0, delta.total_seconds())
        return seconds

    def run(self):
        """Watch a path and log the events."""
        LOG.verbose(f"Started {self.NAME} thread.")  # type: ignore
        with self._cond:
            while not self._stop_event.is_set():
                timeout = self._get_timeout()
                LOG.verbose(  # type: ignore
                    f"Waiting {precisedelta(timeout)} until next maintenance."
                )
                self._cond.wait(timeout=timeout)
                if self._stop_event.is_set():
                    break

                try:
                    LIBRARIAN_QUEUE.put(VacuumTask())
                    LIBRARIAN_QUEUE.put(BackupTask())
                    LIBRARIAN_QUEUE.put(UpdateTask(force=False))
                except Exception as exc:
                    LOG.exception(exc)
                CRON_TIMESTAMP.touch(exist_ok=True)
                sleep(2)
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


def janitor(task):
    """Run Janitor tasks as the librarian process directly."""
    if isinstance(task, VacuumTask):
        vacuum_db()
    elif isinstance(task, BackupTask):
        backup_db()
    elif isinstance(task, UpdateTask):
        update_codex()
    elif isinstance(task, RestartTask):
        restart_codex()
    else:
        LOG.warning(f"Janitor received unknown task {task}")

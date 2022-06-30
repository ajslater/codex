"""Perform maintence tasks."""
from datetime import datetime, time, timedelta
from threading import Condition, Event
from time import sleep

from django.utils import timezone
from humanize import precisedelta

from codex.librarian.janitor.cleanup import cleanup_fks
from codex.librarian.janitor.search import clean_old_queries
from codex.librarian.janitor.update import restart_codex, update_codex
from codex.librarian.janitor.vacuum import backup_db, vacuum_db
from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BackupTask,
    CleanFKsTask,
    CleanSearchTask,
    CleanupMissingComicCovers,
    RestartTask,
    SearchIndexUpdateTask,
    UpdateTask,
    VacuumTask,
)
from codex.settings.logging import get_logger
from codex.settings.settings import CACHE_PATH
from codex.threads import NamedThread


LOG = get_logger(__name__)
DEBOUNCE = 5
CRON_TIMESTAMP = CACHE_PATH / "crond_timestamp"
ONE_DAY = timedelta(days=1)


class Crond(NamedThread):
    """Run a scheduled service for codex."""

    NAME = "Cron"

    @staticmethod
    def _get_midnight(now, tomorrow=False):
        """Get midnight relative to now."""
        if tomorrow:
            now += ONE_DAY
        day = now.astimezone()
        midnight = datetime.combine(day, time.min).astimezone()
        return midnight

    @classmethod
    def _get_timeout(cls):
        """Get seconds until midnight."""
        now = timezone.now()
        try:
            mtime = CRON_TIMESTAMP.stat().st_mtime
            last_cron = datetime.fromtimestamp(mtime, tz=timezone.utc)
        except FileNotFoundError:
            # get last midnight. Usually only on very first run.
            last_cron = cls._get_midnight(now)

        if now - last_cron < ONE_DAY:
            # wait until next midnight
            next_midnight = cls._get_midnight(now, True)
            delta = next_midnight - now
            seconds = max(0, delta.total_seconds())
        else:
            # it's been too long
            seconds = 0

        return int(seconds)

    def run(self):
        """Watch a path and log the events."""
        try:
            self.run_start()
            with self._cond:
                while not self._stop_event.is_set():
                    timeout = self._get_timeout()
                    LOG.verbose(
                        f"Waiting {precisedelta(timeout)} until next maintenance."
                    )
                    self._cond.wait(timeout=timeout)
                    if self._stop_event.is_set():
                        break

                    try:
                        tasks = [
                            CleanFKsTask(),
                            CleanSearchTask(),
                            VacuumTask(),
                            BackupTask(),
                            UpdateTask(force=False),
                            SearchIndexUpdateTask(False),
                            CleanupMissingComicCovers(),
                        ]
                        for task in tasks:
                            LIBRARIAN_QUEUE.put(task)
                    except Exception as exc:
                        LOG.error(f"Error in {self.NAME}")
                        LOG.exception(exc)
                    CRON_TIMESTAMP.touch(exist_ok=True)
                    sleep(2)
        except Exception as exc:
            LOG.error(f"Error in {self.NAME}")
            LOG.exception(exc)
        LOG.verbose(f"Stopped {self.NAME} thread.")

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
    elif isinstance(task, CleanSearchTask):
        clean_old_queries()
    elif isinstance(task, CleanFKsTask):
        cleanup_fks()
    else:
        LOG.warning(f"Janitor received unknown task {task}")

"""Perform maintence tasks."""
from datetime import datetime, time, timedelta
from threading import Condition, Event
from time import sleep

from django.utils import timezone
from humanize import precisedelta

from codex.librarian.covers.purge import COVER_ORPHAN_FIND_STATUS_KEYS
from codex.librarian.covers.tasks import CoverRemoveOrphansTask
from codex.librarian.janitor.cleanup import (
    CLEANUP_FK_STATUS_KEYS,
    TOTAL_CLASSES,
    cleanup_fks,
)
from codex.librarian.janitor.search import CLEAN_SEARCH_STATUS_KEYS, clean_old_queries
from codex.librarian.janitor.tasks import (
    JanitorBackupTask,
    JanitorCleanFKsTask,
    JanitorCleanSearchTask,
    JanitorClearStatusTask,
    JanitorRestartTask,
    JanitorUpdateTask,
    JanitorVacuumTask,
)
from codex.librarian.janitor.update import (
    UPDATE_CODEX_STATUS_KEYS,
    restart_codex,
    update_codex,
)
from codex.librarian.janitor.vacuum import (
    BACKUP_STATUS_KEYS,
    VACCUM_STATUS_KEYS,
    backup_db,
    vacuum_db,
)
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.search.searchd import UPDATE_SEARCH_INDEX_KEYS
from codex.librarian.search.tasks import SearchIndexJanitorUpdateTask
from codex.librarian.status import librarian_status_done, librarian_status_update
from codex.models import Timestamp
from codex.settings.logging import get_logger
from codex.threads import NamedThread


LOG = get_logger(__name__)
DEBOUNCE = 5
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
            mtime = Timestamp.get(Timestamp.JANITOR)
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

    @staticmethod
    def _init_librarian_status():
        librarian_status_update(CLEANUP_FK_STATUS_KEYS, 0, TOTAL_CLASSES, notify=False)
        librarian_status_update(CLEAN_SEARCH_STATUS_KEYS, 0, None, notify=False)
        librarian_status_update(VACCUM_STATUS_KEYS, 0, None, notify=False)
        librarian_status_update(BACKUP_STATUS_KEYS, 0, None, notify=False)
        librarian_status_update(UPDATE_CODEX_STATUS_KEYS, 0, None, notify=False)
        librarian_status_update(UPDATE_SEARCH_INDEX_KEYS, 0, None, notify=False)
        librarian_status_update(COVER_ORPHAN_FIND_STATUS_KEYS, 0, None)

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

                    self._init_librarian_status()
                    try:
                        tasks = [
                            JanitorCleanFKsTask(),
                            JanitorCleanSearchTask(),
                            JanitorVacuumTask(),
                            JanitorBackupTask(),
                            JanitorUpdateTask(force=False),
                            SearchIndexJanitorUpdateTask(False),
                            CoverRemoveOrphansTask(),
                        ]
                        for task in tasks:
                            LIBRARIAN_QUEUE.put(task)
                    except Exception as exc:
                        LOG.error(f"Error in {self.NAME}")
                        LOG.exception(exc)
                    Timestamp.touch(Timestamp.JANITOR)
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


def clear_status():
    """Clear all librarian statuses."""
    librarian_status_done([])


def janitor(task):
    """Run Janitor tasks as the librarian process directly."""
    try:
        if isinstance(task, JanitorVacuumTask):
            vacuum_db()
        elif isinstance(task, JanitorBackupTask):
            backup_db()
        elif isinstance(task, JanitorUpdateTask):
            update_codex()
        elif isinstance(task, JanitorRestartTask):
            restart_codex()
        elif isinstance(task, JanitorCleanSearchTask):
            clean_old_queries()
        elif isinstance(task, JanitorCleanFKsTask):
            cleanup_fks()
        elif isinstance(task, JanitorClearStatusTask):
            clear_status()
        else:
            LOG.warning(f"Janitor received unknown task {task}")
    except Exception as exc:
        LOG.error("Janitor task crashed.")
        LOG.exception(exc)

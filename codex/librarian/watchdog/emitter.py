"""A Codex database event emitter for use by the observer."""

from multiprocessing.queues import Queue
from pathlib import Path
from threading import Condition

from django.db.models.functions import Now
from django.utils import timezone
from humanize import naturaldelta
from typing_extensions import override
from watchdog.events import FileSystemEvent
from watchdog.observers.api import (
    DEFAULT_EMITTER_TIMEOUT,
    EventEmitter,
    EventQueue,
    ObservedWatch,
)
from watchdog.utils.dirsnapshot import DirectorySnapshot

from codex.librarian.watchdog.const import (
    ATTR_EVENT_MAP,
    DIR_NOT_FOUND_TIMEOUT,
    DOCKER_UNMOUNTED_FN,
)
from codex.librarian.watchdog.db_snapshot import CodexDatabaseSnapshot
from codex.librarian.watchdog.dir_snapshot_diff import CodexDirectorySnapshotDiff
from codex.librarian.watchdog.events import (
    FinishPollEvent,
    StartPollEvent,
)
from codex.librarian.watchdog.handlers import (
    CodexCustomCoverEventHandler,
    CodexLibraryEventHandler,
)
from codex.librarian.watchdog.status import WatchdogPollStatus
from codex.librarian.worker import WorkerStatusMixin
from codex.models import Library


def extend_event_filter(
    event_filter: list[type[FileSystemEvent]] | None,
    extended_event_filter: tuple[type[FileSystemEvent], ...],
):
    """Initialize event filter with a some constant types."""
    if event_filter is None:
        event_filter = []
    for event_type in extended_event_filter:
        if event_type not in event_filter:
            event_filter.append(event_type)


class DatabasePollingEmitter(EventEmitter, WorkerStatusMixin):
    """Dispatch an Importer Task from an diff without serializing back into the queue."""

    def __init__(  # noqa: PLR0913
        self,
        event_queue: EventQueue,
        watch: ObservedWatch,
        *,
        logger_,
        librarian_queue: Queue,
        library_id: int,
        db_write_lock,
        covers_only=False,
        timeout: float = DEFAULT_EMITTER_TIMEOUT,
        event_filter: list[type[FileSystemEvent]] | None = None,
    ):
        """Initialize snapshot methods."""
        self.init_worker(logger_, librarian_queue, db_write_lock)
        self._poll_cond = Condition()
        self._force = False
        self._manual_poll = False
        self._watch_path = Path(watch.path)
        self._watch_path_unmounted = self._watch_path / DOCKER_UNMOUNTED_FN
        self._covers_only = covers_only
        self._handler = (
            CodexCustomCoverEventHandler if covers_only else CodexLibraryEventHandler
        )
        self._library_id = library_id

        super().__init__(event_queue, watch, timeout=timeout, event_filter=event_filter)

        self._take_dir_snapshot = lambda: DirectorySnapshot(
            self._watch.path,
            recursive=self.watch.is_recursive,
            # default stat and listdir params
        )

    @staticmethod
    def _get_poll_timeout(library):
        since_last_poll = timezone.now() - library.last_poll
        return max(
            0,
            library.poll_every.total_seconds() - since_last_poll.total_seconds(),
        )

    def _get_timeout(self) -> int | None:
        """Return a special timeout value if there's a problem with the watch dir."""
        msg = ""
        log_level = "WARNING"
        library = Library.objects.get(path=self.watch.path)
        if not library.poll:
            # Wait forever. Manual poll only
            log_level = "INFO"
            msg = f"Library {self._watch_path} waiting for manual poll."
            timeout = None
        elif not self._watch_path.is_dir():
            msg = f"Library {self._watch_path} not found. Not Polling."
            timeout = DIR_NOT_FOUND_TIMEOUT
        elif self._watch_path_unmounted.exists():
            # Maybe overkill of caution here
            msg = f"Library {self._watch_path} looks like an unmounted docker volume. Not polling."
            timeout = DIR_NOT_FOUND_TIMEOUT
        elif not tuple(self._watch_path.iterdir()):
            # Maybe overkill of caution here too
            msg = f"{self._watch_path} is empty. Suspect it may be unmounted. Not polling."
            timeout = DIR_NOT_FOUND_TIMEOUT
        elif library.update_in_progress:
            log_level = "DEBUG"
            msg = f"Library {library.path} update in progress. Not polling."
            timeout = self._get_poll_timeout(library)
        elif self._manual_poll:
            log_level = "DEBUG"
            msg = f"Manual poll requested for {library.path}"
            self._manual_poll = False
            timeout = 0
        elif library.last_poll:
            timeout = self._get_poll_timeout(library)
        else:
            msg = f"First ever poll for {library.path}"
            log_level = "DEBUG"
            timeout = 0

        if msg:
            self.log.log(log_level, msg)

        return timeout

    @property
    @override
    def timeout(self) -> int | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Get the timeout for this emitter from its library."""
        # The timeout from the constructor, self._timeout, is thrown away in favor
        # of a dynamic timeout from the database.
        try:
            return self._get_timeout()
        except Exception:
            timeout = 0
            self.log.exception(f"Getting timeout for {self.watch.path}")
        return timeout

    def _is_take_snapshot(self, timeout):
        """Determine if we should take a snapshot."""
        with self._poll_cond:
            if timeout:
                self.log.debug(
                    f"Polling {self.watch.path} again in {naturaldelta(timeout)}."
                )
            self._poll_cond.wait(timeout)

        # Zero or None are acceptable timeouts to run now.
        return self.should_keep_running() and not self._get_timeout()

    def _take_db_snapshot(self):
        """Get a database snapshot with optional force argument."""
        return CodexDatabaseSnapshot(
            self.watch.path,
            logger_=self.log,
            force=self._force,
            covers_only=self._covers_only,
        )

    def _get_diff(self):
        """Take snapshots and compute the diff."""
        # Get event diff between database snapshot and directory snapshot.
        # Update snapshot.
        db_snapshot = self._take_db_snapshot()
        dir_snapshot = self._take_dir_snapshot()

        if len(dir_snapshot.paths) <= 1:
            # Maybe overkill of caution here also
            self.log.warning(f"{self._watch_path} dir snapshot is empty. Not polling")
            self.log.debug(f"{dir_snapshot.paths=}")
            return None

        # Ignore device for docker and other complex filesystems
        return CodexDirectorySnapshotDiff(
            db_snapshot, dir_snapshot, ignore_device=True, inode_only_modified=True
        )

    def _queue_events(self):
        """Create and queue the events from the diff."""
        diff = self._get_diff()
        if not diff or diff.is_empty():
            reason = f"Nothing changed for {self.watch.path} not sending anything."
            self.log.debug(reason)
            return
        reason = (
            f"Poller sending unfiltered files: {len(diff.files_deleted)} "
            f"deleted, {len(diff.files_modified)} modified, "
            f"{len(diff.files_created)} created, "
            f"{len(diff.files_moved)} moved. "
            f"Poller sending comic folders: {len(diff.dirs_deleted)} deleted,"
            f" {len(diff.dirs_modified)} modified,"
            f" {len(diff.dirs_moved)} moved."
        )
        self.log.debug(reason)
        self.queue_event(StartPollEvent("", force=self._force))

        for attr, event_class in ATTR_EVENT_MAP.items():
            if attr.endswith("moved"):
                for src_path, dest_path in getattr(diff, attr):
                    self.queue_event(event_class(src_path, dest_path))
            else:
                for src_path in getattr(diff, attr):
                    self.queue_event(event_class(src_path))

        self.queue_event(FinishPollEvent("", force=self._force))

    @override
    def queue_events(self, timeout):
        """
        Like PollingEmitter but use a fresh db snapshot and send an entire import task.

        Importantly do not put ti on the actual event_queue because it will adding the
        check_metadata_mtime flag on the import task.
        """
        # We don't want to hit the disk continuously.
        # timeout behaves like an interval for polling emitters.
        if not self._is_take_snapshot(timeout):
            self._force = False
            return
        if self.db_write_lock.locked():
            self.log.warning("Database locked, not polling {self.watch.path}.")
            return
        status = WatchdogPollStatus(subtitle=self.watch.path)
        try:
            self.status_controller.start(status)
            self.log.debug(f"Polling {self.watch.path}...")
            self._queue_events()
            library = Library.objects.get(path=self.watch.path)
            library.last_poll = Now()
            library.save()
        except Exception:
            self.log.exception("poll for watchdog events and queue them")
            raise
        finally:
            self.status_controller.finish(status, clear_subtitle=False)
            # Reset on poll()
            self._force = False

    @override
    def on_thread_stop(self):
        """Send the poller as well."""
        with self._poll_cond:
            self._poll_cond.notify()

    def poll(self, *, force: bool):
        """Poll now, sooner than timeout."""
        self._force = force
        self._manual_poll = True
        with self._poll_cond:
            self._poll_cond.notify()

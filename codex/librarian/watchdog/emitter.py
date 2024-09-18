"""A Codex database event emitter for use by the observer."""

from logging import DEBUG, WARNING
from pathlib import Path
from threading import Condition

from django.db.models.functions import Now
from django.utils import timezone
from humanize import naturaldelta
from watchdog.events import (
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)
from watchdog.observers.api import DEFAULT_EMITTER_TIMEOUT, EventEmitter
from watchdog.utils.dirsnapshot import DirectorySnapshot

from codex.librarian.watchdog.db_snapshot import CodexDatabaseSnapshot
from codex.librarian.watchdog.dir_snapshot_diff import CodexDirectorySnapshotDiff
from codex.librarian.watchdog.status import WatchdogStatusTypes
from codex.models import Library
from codex.status import Status
from codex.worker_base import WorkerBaseMixin

_CODEX_EVENT_FILTER = [
    FileMovedEvent,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    # FileClosedEvent,
    # FileOpenedEvent,
    DirMovedEvent,
    DirModifiedEvent,
    DirDeletedEvent,
    # DirCreatedEvent,
]
_DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"


class DatabasePollingEmitter(EventEmitter, WorkerBaseMixin):
    """Use DatabaseSnapshots to compare against the DirectorySnapshots."""

    _DIR_NOT_FOUND_TIMEOUT = 15 * 60

    def __init__(  # noqa PLR0913
        self,
        event_queue,
        watch,
        timeout=DEFAULT_EMITTER_TIMEOUT,
        log_queue=None,
        librarian_queue=None,
        covers_only=False,
    ):
        """Initialize snapshot methods."""
        self.init_worker(log_queue, librarian_queue)
        self._poll_cond = Condition()
        self._force = False
        self._watch_path = Path(watch.path)
        self._watch_path_unmounted = self._watch_path / _DOCKER_UNMOUNTED_FN
        self._covers_only = covers_only
        super().__init__(
            event_queue, watch, timeout=timeout, event_filter=_CODEX_EVENT_FILTER
        )

        self._take_dir_snapshot = lambda: DirectorySnapshot(
            self._watch.path,
            recursive=self.watch.is_recursive,
            # default stat and listdir params
        )

    def poll(self, force=False):
        """Poll now, sooner than timeout."""
        self._force = force
        with self._poll_cond:
            self._poll_cond.notify()

    def _take_db_snapshot(self):
        """Get a database snapshot with optional force argument."""
        db_snapshot = CodexDatabaseSnapshot(
            self.watch.path,
            self.watch.is_recursive,
            force=self._force,
            log_queue=self.log_queue,
            covers_only=self._covers_only,
        )
        self._force = False
        return db_snapshot

    def _is_watch_path_ok(self, library):
        """Return a special timeout value if there's a problem with the watch dir."""
        ok = False
        msg = ""
        log_level = WARNING
        if not library.poll:
            # Wait forever. Manual poll only
            ok = None
        elif not self._watch_path.is_dir():
            msg = f"Library {self._watch_path} not found. Not Polling."
        elif self._watch_path_unmounted.exists():
            # Maybe overkill of caution here
            msg = f"Library {self._watch_path} looks like an unmounted docker volume. Not polling."
        elif not tuple(self._watch_path.iterdir()):
            # Maybe overkill of caution here too
            msg = f"{self._watch_path} is empty. Suspect it may be unmounted. Not polling."
        elif library.update_in_progress:
            msg = f"Library {library.path} update in progress. Not polling."
            log_level = DEBUG
        else:
            ok = True

        if msg:
            self.log.log(log_level, msg)

        return ok

    @property
    def timeout(self) -> int | None:  # type: ignore
        """Get the timeout for this emitter from its library."""
        # The timeout from the constructor, self._timeout, is thrown away in favor
        # of a dynamic timeout from the database.
        timeout = self._timeout  # default is 1 second
        try:
            library = Library.objects.get(path=self.watch.path)
            ok = self._is_watch_path_ok(library)
            if ok is None:
                self.log.info(f"Library {self._watch_path} waiting for manual poll.")
                return None  # None waits forever.
            if ok is False:
                return self._DIR_NOT_FOUND_TIMEOUT

            if library.last_poll:
                since_last_poll = timezone.now() - library.last_poll
                timeout = max(
                    0,
                    library.poll_every.total_seconds()
                    - since_last_poll.total_seconds(),
                )
        except Exception:
            timeout = 0
            self.log.exception(f"Getting timeout for {self.watch.path}")
        return int(timeout)

    def _is_take_snapshot(self, timeout):
        """Determine if we should take a snapshot."""
        with self._poll_cond:
            if timeout:
                self.log.info(
                    f"Polling {self.watch.path} again in {naturaldelta(timeout)}."
                )
            self._poll_cond.wait(timeout)

        if not self.should_keep_running():
            return None

        library = Library.objects.get(path=self.watch.path)
        ok = self._is_watch_path_ok(library)
        if ok is False:
            self.log.warning("Not Polling.")
            return None
        return library

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

    def _queue_events(self, diff):
        """Create and queue the events from the diff."""
        self.log.debug(
            f"Poller sending unfiltered files: {len(diff.files_deleted)} "
            f"deleted, {len(diff.files_modified)} modified, "
            f"{len(diff.files_created)} created, "
            f"{len(diff.files_moved)} moved."
        )
        self.log.debug(
            f"Poller sending comic folders: {len(diff.dirs_deleted)} deleted,"
            f" {len(diff.dirs_modified)} modified,"
            f" {len(diff.dirs_moved)} moved."
        )
        # Files.
        # Could remove non-comics here, but handled by the EventHandler
        for src_path in diff.files_deleted:
            self.queue_event(FileDeletedEvent(src_path))
        for src_path in diff.files_modified:
            self.queue_event(FileModifiedEvent(src_path))
        for src_path in diff.files_created:
            self.queue_event(FileCreatedEvent(src_path))
        for src_path, dest_path in diff.files_moved:
            self.queue_event(FileMovedEvent(src_path, dest_path))

        # Directories.
        for src_path in diff.dirs_deleted:
            self.queue_event(DirDeletedEvent(src_path))
        for src_path in diff.dirs_modified:
            self.queue_event(DirModifiedEvent(src_path))
        # Folders are only created by comics themselves
        # The event handler excludes DirCreatedEvent as well.
        for src_path, dest_path in diff.dirs_moved:
            self.queue_event(DirMovedEvent(src_path, dest_path))

    def queue_events(self, timeout):
        """Queue events like PollingEmitter but always use a fresh db snapshot."""
        # We don't want to hit the disk continuously.
        # timeout behaves like an interval for polling emitters.
        library = self._is_take_snapshot(timeout)
        if not library:
            return
        status = Status(WatchdogStatusTypes.POLL, subtitle=self.watch.path)
        try:
            self.status_controller.start(status)
            self.log.debug(f"Polling {self.watch.path}...")
            diff = self._get_diff()
            if not diff:
                return

            self._queue_events(diff)

            library.last_poll = Now()
            library.save()

            self.log.info(f"Polled {self.watch.path}")
        except Exception:
            self.log.exception("poll for watchdog events and queue them")
            raise
        finally:
            self.status_controller.finish(status)

    def on_thread_stop(self):
        """Send the poller as well."""
        with self._poll_cond:
            self._poll_cond.notify()

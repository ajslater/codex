"""A Codex database event emitter for use by the observer."""
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
from watchdog.observers.api import EventEmitter
from watchdog.utils.dirsnapshot import DirectorySnapshot

from codex.librarian.watchdog.dirsnapshot import (
    CodexDatabaseSnapshot,
    CodexDirectorySnapshotDiff,
)
from codex.librarian.watchdog.status import WatchdogStatusTypes
from codex.models import Library
from codex.worker_base import WorkerBaseMixin

_DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"


class DatabasePollingEmitter(EventEmitter, WorkerBaseMixin):
    """Use DatabaseSnapshots to compare against the DirectorySnapshots."""

    _DIR_NOT_FOUND_TIMEOUT = 15 * 60

    def __init__(
        self, event_queue, watch, timeout=None, log_queue=None, librarian_queue=None
    ):
        """Initialize snapshot methods."""
        self.init_worker(log_queue, librarian_queue)
        self._poll_cond = Condition()
        self._force = False
        self._watch_path = Path(watch.path)
        self._watch_path_unmounted = self._watch_path / _DOCKER_UNMOUNTED_FN
        super().__init__(event_queue, watch)

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
            self.watch.path, self.watch.is_recursive, force=self._force
        )
        self._force = False
        return db_snapshot

    def _is_watch_path_ok(self, library):
        """Return a special timeout value if there's a problem with the watch dir."""
        if not library.poll:
            # Wait forever. Manual poll only
            return None
        if not self._watch_path.is_dir():
            self.log.warning(f"Library {self._watch_path} not found.")
            return False
        if self._watch_path_unmounted.exists():
            # Maybe overkill of caution here
            self.log.warning(
                f"Library {self._watch_path} looks like an unmounted docker volume."
            )
            return False
        if not tuple(self._watch_path.iterdir()):
            # Maybe overkill of caution here too
            self.log.warning(
                f"{self._watch_path} is empty. Suspect it may be unmounted."
            )
            return False

        return True

    @property
    def timeout(self):
        """Get the timeout for this emitter from its library."""
        # The timeout from the constructor, self._timeout, is thrown away in favor
        # of a dynamic timeout from the database.
        timeout = self._timeout  # default is 1 second
        try:
            library = Library.objects.get(path=self.watch.path)
            ok = self._is_watch_path_ok(library)
            if ok is None:
                self.log.info(f"Library {self._watch_path} waiting for manual poll.")
                return None
            elif ok is False:
                return self._DIR_NOT_FOUND_TIMEOUT

            if library.last_poll:
                since_last_poll = timezone.now() - library.last_poll
                timeout = max(
                    0,
                    library.poll_every.total_seconds()
                    - since_last_poll.total_seconds(),
                )
        except Exception as exc:
            timeout = None
            self.log.error(f"Getting timeout for {self.watch.path}")
            self.log.exception(exc)
        return timeout

    def _is_take_snapshot(self, timeout):
        """Determine if we should take a snapshot."""
        with self._poll_cond:
            if timeout:
                self.log.info(
                    f"Polling {self.watch.path} again in {naturaldelta(timeout)}."
                )
            self._poll_cond.wait(timeout)

        if not self.should_keep_running():
            return

        library = Library.objects.get(path=self.watch.path)
        ok = self._is_watch_path_ok(library)
        if ok is False:
            self.log.warning("Not Polling.")
            return
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
            return

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
        try:
            library = self._is_take_snapshot(timeout)
            if not library:
                return

            self.status_controller.start(WatchdogStatusTypes.POLL, name=self.watch.path)
            self.log.debug(f"Polling {self.watch.path}...")
            diff = self._get_diff()
            if not diff:
                return

            self._queue_events(diff)

            library.last_poll = Now()
            library.save()

            self.log.info(f"Polled {self.watch.path}")
        except Exception as exc:
            self.log.exception(exc)
            raise exc
        finally:
            self.status_controller.finish(WatchdogStatusTypes.POLL)

    def on_thread_stop(self):
        """Send the poller as well."""
        with self._poll_cond:
            self._poll_cond.notify()

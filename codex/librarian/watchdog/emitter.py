"""A Codex database event emitter for use by the observer."""
import os

from itertools import chain
from logging import getLogger
from pathlib import Path
from threading import Condition

from django.db.models.functions import Now
from django.utils import timezone
from humanize import precisedelta
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
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff

from codex.models import Comic, FailedImport, Folder, Library


LOG = getLogger(__name__)
DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"


class CodexDatabaseSnapshot(DirectorySnapshot):
    """Take snapshots from the Codex database."""

    MODELS = (Folder, Comic, FailedImport)

    @classmethod
    def _walk(cls, root):
        """Populate the DirectorySnapshot structures from the database."""
        for model in cls.MODELS:
            yield model.objects.filter(library__path=root).values("path", "stat")

    def _fix_bad_db_stat(self, wp_path, params, stat):
        """Handle null or zeroed out database stat entries."""
        if params and len(params) == 10 and params[1]:
            # params[1] is st_inode, if it's okay most everything else works
            return params
        if Path(wp_path).exists():
            LOG.debug(f"Force modify path with bad db record: {wp_path}")
            params = list(stat(wp_path))
            # Fake mtime will trigger a modified event
            params[8] = 0.0
        else:
            LOG.debug(f"Force delete path with bad db record: {wp_path}")
            # This will trigger a deleted event
            params = Comic.ZERO_STAT
        return params

    def _set_lookups(self, path, st):
        """Populate thte lookup dirs."""
        self._stat_info[path] = st
        i = (st.st_ino, st.st_dev)
        self._inode_to_path[i] = path

    def __init__(
        self,
        path,
        _recursive=True,  # unused, always recursive
        stat=os.stat,
        _listdir=os.listdir,  # unused for database
        force=False,
    ):
        """Initialize like DirectorySnapshot but use a database walk."""
        self._stat_info = {}
        self._inode_to_path = {}
        if not Path(path).is_dir():
            LOG.warning(f"{path} not found, cannot snapshot.")
            return

        # Add the library root
        self._set_lookups(path, stat(path))

        for wp in chain.from_iterable(self._walk(path)):
            wp_path = wp["path"]
            params = self._fix_bad_db_stat(wp_path, wp.get("stat"), stat)
            if force:
                # Fake mtime will trigger modified event
                params[8] = 0
            st = os.stat_result(tuple(params))
            self._set_lookups(wp_path, st)


class DatabasePollingEmitter(EventEmitter):
    """Use DatabaseSnapshots to compare against the DirectorySnapshots."""

    DIR_NOT_FOUND_TIMEOUT = 15 * 60

    def __init__(
        self,
        event_queue,
        watch,
        timeout=None,  # unused, timeout is set dynamically internally
        stat=os.stat,
        listdir=os.listdir,
    ):
        """Initialize snapshot methods."""
        self._poll_cond = Condition()
        self._force = False
        self._watch_path = Path(watch.path)
        self._watch_path_unmounted = self._watch_path / DOCKER_UNMOUNTED_FN
        super().__init__(event_queue, watch)

        self._take_dir_snapshot = lambda: DirectorySnapshot(
            self.watch.path, self.watch.is_recursive, stat=stat, listdir=listdir
        )

    def poll(self, force=False):
        """Poll now, sooner than timeout."""
        if force:
            self._force = True
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
            LOG.warning(f"Library {self._watch_path} not poll enabled.")
            self._stopped_event.set()
            return False, 0
        if not self._watch_path.is_dir():
            LOG.warning(f"Library {self._watch_path} not found.")
            return False, self.DIR_NOT_FOUND_TIMEOUT
        if self._watch_path_unmounted.exists():
            LOG.warning(
                f"Library {self._watch_path} looks like an unmounted docker volume."
            )
            return False, self.DIR_NOT_FOUND_TIMEOUT
        if not tuple(self._watch_path.iterdir()):
            LOG.warning(f"{self._watch_path} is empty. Suspect it may be unmounted.")
            return False, self.DIR_NOT_FOUND_TIMEOUT

        return True, None

    @property
    def timeout(self):
        """Get the timeout for this emitter from its library."""
        library = Library.objects.get(path=self.watch.path)
        ok, timeout = self._is_watch_path_ok(library)
        if not ok:
            return timeout

        if library.last_poll:
            since_last_poll = timezone.now() - library.last_poll
            timeout = max(
                0, library.poll_every.total_seconds() - since_last_poll.total_seconds()
            )

        else:
            timeout = 0
        return timeout

    def queue_events(self, timeout=None):
        """Queue events like PollingEmitter but always use a fresh db snapshot."""
        # We don't want to hit the disk continuously.
        # timeout behaves like an interval for polling emitters.
        with self._poll_cond:
            LOG.verbose(  # type: ignore
                f"Polling {self.watch.path} again in {precisedelta(timeout)}."
            )
            self._poll_cond.wait(timeout)
            if not self.should_keep_running():
                return

            library = Library.objects.get(path=self.watch.path)
            ok, _ = self._is_watch_path_ok(library)
            if not ok:
                LOG.warning("Not Polling.")
                return
            LOG.verbose(f"Polling {self.watch.path}...")  # type: ignore

            # Get event diff between database snapshot and directory snapshot.
            # Update snapshot.
            db_snapshot = self._take_db_snapshot()
            dir_snapshot = self._take_dir_snapshot()

            if len(dir_snapshot.paths) <= 1:
                LOG.warning(f"{self._watch_path} dir snapshot is empty. Not polling")
                LOG.verbose(f"{dir_snapshot.paths=}")  # type: ignore
                return

            events = DirectorySnapshotDiff(db_snapshot, dir_snapshot)
            LOG.debug(events)

            # Files.
            # Could remove non-comics here, but handled by the EventHandler
            for src_path in events.files_deleted:
                self.queue_event(FileDeletedEvent(src_path))
            for src_path in events.files_modified:
                self.queue_event(FileModifiedEvent(src_path))
            for src_path in events.files_created:
                self.queue_event(FileCreatedEvent(src_path))
            for src_path, dest_path in events.files_moved:
                self.queue_event(FileMovedEvent(src_path, dest_path))

            # Directories.
            for src_path in events.dirs_deleted:
                self.queue_event(DirDeletedEvent(src_path))
            for src_path in events.dirs_modified:
                self.queue_event(DirModifiedEvent(src_path))
            # Folders are only created by comics themselves
            # The event handler excludes these but skip it here too.
            # for src_path in events.dirs_created:
            #    self.queue_event(DirCreatedEvent(src_path))
            #
            for src_path, dest_path in events.dirs_moved:
                self.queue_event(DirMovedEvent(src_path, dest_path))

            Library.objects.filter(path=self.watch.path).update(
                last_poll=Now(), updated_at=Now()
            )
        LOG.verbose(f"Polling {self.watch.path} finished.")  # type: ignore

    def on_thread_stop(self):
        """Send the poller as well."""
        with self._poll_cond:
            self._poll_cond.notify()

"""Database polling for library changes."""

from pathlib import Path
from threading import Condition, Event
from typing import override

from django.db.models.functions import Now
from django.utils import timezone
from humanize import naturaldelta

from codex.librarian.fs.poller.events import PollEvent, PollEventType
from codex.librarian.fs.poller.snapshot import DatabaseSnapshot, DiskSnapshot
from codex.librarian.fs.poller.snapshot_diff import SnapshotDiff
from codex.librarian.fs.poller.status import FSPollStatus
from codex.librarian.fs.poller.tasks import FSPollLibrariesTask
from codex.librarian.fs.tasks import FSEventTask
from codex.librarian.threads import NamedThread
from codex.librarian.worker import WorkerStatusMixin
from codex.models import Library
from codex.views.const import EPOCH_START

DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"
_DIR_NOT_FOUND_TIMEOUT = 15 * 60
_LIBRARY_ONLY = (
    "path",
    "poll",
    "poll_every",
    "last_poll",
    "update_in_progress",
    "covers_only",
)


class LibraryPollerThread(NamedThread, WorkerStatusMixin):
    """Poll libraries on a schedule, comparing DB snapshots against disk."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the poller."""
        super().__init__(*args, **kwargs)
        self.daemon = True
        self._cond = Condition()
        self._shutdown_event = Event()
        self._pending_poll_ids: frozenset[int] = frozenset()
        self._pending_force: bool = False

    #############################################
    # Public interface - called from librariand #
    #############################################

    def wake(self) -> None:
        """Wake up the poller after library config changes."""
        with self._cond:
            self._cond.notify()

    def poll(self, task: FSPollLibrariesTask) -> None:
        """Trigger an immediate poll for specific libraries."""
        with self._cond:
            self._pending_poll_ids = task.library_ids or frozenset(
                Library.objects.values_list("id", flat=True)
            )
            self._pending_force = task.force
            self._cond.notify()

    def stop(self) -> None:
        """Signal the poller to shut down."""
        self._shutdown_event.set()
        with self._cond:
            self._cond.notify()

    #######################
    # Timeout computation #
    #######################

    def _get_poll_timeout(self, library: Library) -> float | None:  # noqa: PLR0911
        """
        Compute seconds until this library's next scheduled poll.

        Returns None to wait forever (manual poll only).
        """
        watch_path = Path(library.path)
        unmounted_marker = watch_path / DOCKER_UNMOUNTED_FN

        if not library.poll:
            self.log.info(f"Library {library.path} waiting for manual poll.")
            return None

        if not watch_path.is_dir():
            self.log.warning(f"Library {library.path} not found. Not polling.")
            return _DIR_NOT_FOUND_TIMEOUT

        if unmounted_marker.exists():
            warning = f"Library {library.path} looks like an unmounted docker volume. Not polling."
            self.log.warning(warning)
            return _DIR_NOT_FOUND_TIMEOUT

        if not tuple(watch_path.iterdir()):
            self.log.warning(
                f"{library.path} is empty. Suspect unmounted. Not polling."
            )
            return _DIR_NOT_FOUND_TIMEOUT

        if library.update_in_progress:
            self.log.debug(f"Library {library.path} update in progress. Not polling.")
            return self._seconds_until_poll(library)

        if not library.last_poll:
            self.log.debug(f"First ever poll for {library.path}")
            return 0

        return self._seconds_until_poll(library)

    @staticmethod
    def _seconds_until_poll(library: Library) -> float:
        """Seconds remaining until the next scheduled poll."""
        last_poll = library.last_poll or EPOCH_START
        since_last = timezone.now() - last_poll
        return max(0, library.poll_every.total_seconds() - since_last.total_seconds())

    ######################################
    # Snapshot diff and event generation #
    ######################################

    def _get_diff(self, library: Library, *, force: bool) -> SnapshotDiff | None:
        """Compute the diff between DB and disk for a library."""
        covers_only = library.covers_only
        ignore_device = True
        db_snap = DatabaseSnapshot(
            library.path,
            self.log,
            covers_only=covers_only,
            ignore_device=ignore_device,
            force=force,
        )
        disk_snap = DiskSnapshot(
            library.path, self.log, covers_only=covers_only, ignore_device=ignore_device
        )

        if len(disk_snap.paths) <= 1:
            self.log.warning(f"{library.path} dir snapshot is empty. Not polling.")
            return None

        return SnapshotDiff(db_snap, disk_snap)

    def _queue_poll_events(self, library: Library, *, force: bool) -> None:
        """Run the snapshot diff and queue resulting events."""
        diff = self._get_diff(library, force=force)
        if not diff or diff.is_empty():
            self.log.debug(f"Nothing changed for {library.path}")
            return

        debug_log = (
            f"Poller found: {len(diff.files_deleted)} deleted, "
            f"{len(diff.files_modified)} modified, "
            f"{len(diff.files_added)} added, "
            f"{len(diff.files_moved)} moved files. "
            f"{len(diff.dirs_deleted)} deleted, "
            f"{len(diff.dirs_modified)} modified, "
            f"{len(diff.dirs_moved)} moved dirs."
        )
        self.log.debug(debug_log)

        pk = library.pk
        # Signal batcher: poll starting
        start = FSEventTask(pk, PollEvent(PollEventType.start, force=force))
        self.librarian_queue.put(start)

        # Send all diff events
        for event in diff.to_events():
            task = FSEventTask(pk, event)
            self.librarian_queue.put(task)

        # Signal batcher: poll finished — flush the batch
        finish = FSEventTask(pk, PollEvent(PollEventType.finish, force=force))
        self.librarian_queue.put(finish)

    def _poll_library(self, library: Library, *, force: bool) -> None:
        """Poll a single library with status tracking."""
        if self.db_write_lock.locked():
            self.log.warning(f"Database locked, not polling {library.path}.")
            return
        status = FSPollStatus(subtitle=library.path)
        try:
            self.status_controller.start(status)
            self.log.debug(f"Polling {library.path}...")
            self._queue_poll_events(library, force=force)
            library.last_poll = Now()
            library.save()
        except Exception:
            self.log.exception(f"Poll {library.path}")
        finally:
            self.status_controller.finish(status)

    #############
    # Main loop #
    #############

    def _get_min_timeout(self) -> float | None:
        """Find the shortest timeout across all polled libraries."""
        min_timeout: float | None = None
        try:
            libraries = Library.objects.all().only(*_LIBRARY_ONLY)
            for library in libraries:
                try:
                    timeout = self._get_poll_timeout(library)
                except FileNotFoundError:
                    self.log.warning(f"Library {library.path} not found.")
                    continue

                if timeout is None:
                    continue
                if timeout == 0:
                    return 0
                if min_timeout is None or timeout < min_timeout:
                    min_timeout = timeout
        except Exception:
            self.log.exception("Computing next poll timeout")
            return 60  # Retry in a minute on error

        return min_timeout

    def _poll_due_libraries(self, *, force: bool = False) -> None:
        """Poll all libraries that are due."""
        try:
            libraries = Library.objects.all().only(*_LIBRARY_ONLY)
            for library in libraries:
                try:
                    timeout = self._get_poll_timeout(library)
                except FileNotFoundError:
                    continue
                if timeout is not None and timeout <= 0:
                    self._poll_library(library, force=force)
        except Exception:
            self.log.exception("Polling due libraries")

    def _handle_pending_polls(self) -> None:
        """Handle manually triggered polls."""
        poll_ids = self._pending_poll_ids
        force = self._pending_force
        self._pending_poll_ids = frozenset()
        self._pending_force = False

        try:
            qs = Library.objects.all()
            if poll_ids:
                qs = qs.filter(pk__in=poll_ids)
            qs.only(*_LIBRARY_ONLY)
            for library in qs:
                self._poll_library(library, force=force)
        except Exception:
            self.log.exception(f"Manual library poll {poll_ids}")

    @override
    def run(self) -> None:
        """Poller main loop."""
        self.run_start()

        while not self._shutdown_event.is_set():
            try:
                # Handle any pending manual polls first
                if self._pending_poll_ids:
                    self._handle_pending_polls()

                # Find the next scheduled poll time
                timeout = self._get_min_timeout()
                if timeout is not None and timeout <= 0:
                    self._poll_due_libraries()
                    continue

                # Sleep until next poll or until woken
                if timeout is not None:
                    self.log.debug(f"Next poll in {naturaldelta(timeout)}.")
                with self._cond:
                    self._cond.wait(timeout)

            except Exception:
                self.log.exception(f"{self.__class__.__name__} loop error")

        self.log.debug(f"Stopped {self.__class__.__name__}")

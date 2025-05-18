"""A Codex database event emitter for use by the observer."""

from django.db.models.functions import Now
from django.utils import timezone
from humanize import naturaldelta
from typing_extensions import override

from codex.librarian.status import Status
from codex.librarian.watchdog.db_snapshot import CodexDatabaseSnapshot
from codex.librarian.watchdog.dir_snapshot_diff import CodexDirectorySnapshotDiff
from codex.librarian.watchdog.emitter_dispatcher import DatabasePollingEmitterDispatcher
from codex.librarian.watchdog.status import WatchdogStatusTypes
from codex.models import Library

_DIR_NOT_FOUND_TIMEOUT = 15 * 60


class DatabasePollingEmitter(DatabasePollingEmitterDispatcher):
    """Use DatabaseSnapshots to compare against the DirectorySnapshots."""

    def _is_watch_path_ok(self, library):
        """Return a special timeout value if there's a problem with the watch dir."""
        ok = False
        msg = ""
        log_level = "WARNING"
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
            log_level = "DEBUG"
        else:
            ok = True

        if msg:
            self.log.log(log_level, msg)

        return ok

    @property
    @override
    def timeout(self) -> float | None:  # pyright: ignore[reportIncompatibleMethodOverride]
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
                return _DIR_NOT_FOUND_TIMEOUT

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

    @override
    def queue_events(self, timeout):
        """
        Like PollingEmitter but use a fresh db snapshot and send an entire import task.

        Importantly do not put ti on the actual event_queue because it will adding the
        check_metadata_mtime flag on the import task.
        """
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

            self.dispatch_import_task(diff)

            library.last_poll = Now()
            library.save()

            self.log.success(f"Polled {self.watch.path}")
        except Exception:
            self.log.exception("poll for watchdog events and queue them")
            raise
        finally:
            self.status_controller.finish(status)
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
        with self._poll_cond:
            self._poll_cond.notify()

"""Filesystem watcher using watchfiles."""

from pathlib import Path
from threading import Event
from time import sleep
from typing import override

from watchfiles import Change, watch

from codex.librarian.fs.filters import (
    match_comic,
    match_folder_cover,
    match_group_cover_image,
)
from codex.librarian.fs.tasks import FSEventTask
from codex.librarian.fs.watcher.events import process_changes
from codex.librarian.fs.watcher.status import FSWatcherRestartStatus
from codex.librarian.threads import NamedThread
from codex.models import Library

_MAX_PATH_WATCH_RETRIES = 1


class CodexWatchFilter:
    """Watchfiles watcher class for both types of library."""

    def __init__(self, covers_only_paths: set[str]):
        """Set covers_only_paths."""
        self._covers_only_paths = covers_only_paths

    def __call__(self, change: Change, path: str) -> bool:
        """
        Filter method.

        Deleted paths can't be inspected on disk, so let them all through;
        event processing filters by DB lookup and suffix matching instead.
        """
        if change == Change.deleted:
            return True

        ppath = Path(path)
        covers_only = False
        for covers_only_path in self._covers_only_paths:
            if ppath.is_relative_to(covers_only_path):
                covers_only = True
                break

        if covers_only:
            return match_group_cover_image(ppath)
        return ppath.is_dir() or match_comic(ppath) or match_folder_cover(ppath)


class LibraryWatcherThread(NamedThread):
    """Watch all event-enabled library paths for filesystem changes."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the watcher."""
        super().__init__(*args, **kwargs)
        self.daemon = True
        self._library_paths: dict[str, int] = {}  # path to library_pk
        self._covers_only_paths: set[str] = set()
        self._restart_event = Event()
        self._shutdown_event = Event()

    def _log_update_paths_from_db(self, new_paths_dict: dict[str, int]):
        old_paths = frozenset(self._library_paths.keys())
        new_paths = frozenset(new_paths_dict.keys())

        if old_paths == new_paths:
            return
        added = new_paths - old_paths
        removed = old_paths - new_paths
        if added:
            self.log.info(f"FS adding paths: {added}")
        if removed:
            self.log.info(f"FS removing paths: {removed}")

    def _update_paths_from_db(self) -> None:
        """Query the database for current library paths to watch."""
        new_paths_dict: dict[str, int] = {}
        new_covers: set[str] = set()
        try:
            libraries = (
                Library.objects.filter(events=True)
                .all()
                .only("pk", "path", "covers_only")
            )
            for library in libraries:
                try:
                    new_paths_dict[library.path] = library.pk
                    if library.covers_only:
                        new_covers.add(library.path)
                except Exception:
                    self.log.exception(f"Processing library {library.pk}")
        except Exception:
            self.log.exception("Querying libraries for watcher")
            return

        self._log_update_paths_from_db(new_paths_dict)

        self._library_paths = new_paths_dict
        self._covers_only_paths = new_covers

    #############################################
    # Public interface - called from librariand #
    #############################################

    def restart(self) -> None:
        """Update watched paths from the database."""
        status = FSWatcherRestartStatus()
        try:
            self.status_controller.start(status)
            self._update_paths_from_db()
            self._restart_event.set()
        finally:
            self.status_controller.finish(status)

    #############
    # Main loop #
    #############

    def _process_changes(self, changes: set[tuple[Change, str]]) -> None:
        """Route watchfiles changes through processing to the librarian queue."""
        # Watchfiles does not expand events for added or removed directories or do move detection
        # So handle this myself.
        for library_pk, event in process_changes(
            changes, self._library_paths, self._covers_only_paths
        ):
            task = FSEventTask(library_pk, event)
            self.librarian_queue.put(task)

    def _get_extant_paths(self, paths: list[str]) -> list[str]:
        extant_paths = []
        for path in paths:
            retry = 0
            while retry <= _MAX_PATH_WATCH_RETRIES:
                if Path(path).is_dir():
                    extant_paths.append(path)
                    level = "INFO" if retry else "DEBUG"
                    self.log.log(level, f"Watching {path}")
                    break
                self.log.warning(f"Waiting 5 seconds for {path} to appear...")
                sleep(5)
                retry += 1
            else:
                self.log.warning(f"{path} does not seem to exist, not watching.")

        plural = "s" if len(extant_paths) != 1 else ""
        self.log.info(f"Watching {len(extant_paths)} library path{plural} for events.")
        return extant_paths

    def _watch_loop(self) -> None:
        """Run the watchfiles loop, restarting when paths change."""
        watch_filter = CodexWatchFilter(self._covers_only_paths)
        while not self._shutdown_event.is_set():
            self._restart_event.clear()
            paths = list(self._library_paths.keys())
            if not paths:
                # No paths to watch — wait for a sync signal
                self._restart_event.wait(timeout=5.0)
                continue
            extant_paths = self._get_extant_paths(paths)
            try:
                for changes in watch(
                    *extant_paths,
                    stop_event=self._restart_event,
                    recursive=True,
                    watch_filter=watch_filter,
                ):
                    if self._shutdown_event.is_set():
                        return
                    self._process_changes(changes)
            except FileNotFoundError as exc:
                self.log.warning(f"Watch path disappeared: {exc}")
            except Exception:
                self.log.exception("FS error")

    @override
    def run(self) -> None:
        """Thread entry point."""
        self.run_start()
        self._update_paths_from_db()
        self._watch_loop()
        self.log.debug(f"Stopped {self.__class__.__name__}")

    def stop(self) -> None:
        """Signal the watcher to shut down."""
        self._shutdown_event.set()
        self._restart_event.set()  # Unblock if waiting

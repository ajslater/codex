"""Watch librarys recursively for changes."""
import logging
import os
import time

from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from codex.librarian.importer import COMIC_MATCHER
from codex.librarian.queue import QUEUE
from codex.librarian.queue import ComicDeletedTask
from codex.librarian.queue import ComicModifiedTask
from codex.librarian.queue import ComicMovedTask
from codex.librarian.queue import FolderDeletedTask
from codex.librarian.queue import FolderMovedTask
from codex.models import Library


LOG = logging.getLogger(__name__)


class CodexLibraryEventHandler(FileSystemEventHandler):
    """Handle watchdog events for comics in a library."""

    EVENT_DELAY = 1

    def __init__(self, library_pk, *args, **kwargs):
        """Let us send along he library id."""
        self.pk = library_pk
        super().__init__(*args, **kwargs)

    @staticmethod
    def is_ignored(is_dir, path):
        """Determine if we should ignore this event."""
        return not is_dir and COMIC_MATCHER.search(path) is None

    @staticmethod
    def get_size(path, is_dir):
        """Get the size of a file or directory."""
        path = Path(path)
        if is_dir:
            size = 0
            for root, _, fns in os.walk(path):
                rp = Path(root)
                for fn in fns:
                    full_path = Path(rp / fn)
                    size += CodexLibraryEventHandler.get_size(full_path, False)
        else:
            size = path.stat().st_size
        return size

    @classmethod
    def _wait_for_copy(cls, path, is_dir):
        """
        Wait for a file to stay the same size.

        Watchdog events fire on the start of the copy. On slow or network
        filesystems, this sends an event before the file is finished
        copying.
        """
        old_size = -1
        while True:
            new_size = cls.get_size(path, is_dir)
            if old_size == new_size:
                break
            old_size = cls.get_size(path, is_dir)
            time.sleep(cls.EVENT_DELAY)

    @classmethod
    def _wait_for_delete(cls, path):
        """Wait for a delete to finish."""
        while Path(path).exists():
            time.sleep(cls.EVENT_DELAY)

    def on_modified(self, event):
        """Put a comic modified task on the queue."""
        if event.is_directory or self.is_ignored(event.is_directory, event.src_path):
            return

        src_path = Path(event.src_path)
        self._wait_for_copy(src_path, event.is_directory)
        task = ComicModifiedTask(event.src_path, self.pk)
        QUEUE.put(task)

    def on_created(self, event):
        """Do the same thing as for modified."""
        self.on_modified(event)

    def on_moved(self, event):
        """
        Put a comic moved task on the queue.

        Watchdog events can arrive in any order, but often file events
        occur before folder events. This ends up leading us to create
        new folders and delete old ones on move instead of moving the
        folders. The solution is to implement lazydog in a cross platform
        manner. Make a delay queue for all events and see if they can
        be bundled as a single top-level folder move event.
        For the future.
        """
        if self.is_ignored(event.is_directory, event.dest_path):
            return

        self._wait_for_copy(event.dest_path, event.is_directory)
        if event.is_directory:
            task = FolderMovedTask(event.src_path, event.dest_path)
        else:
            task = ComicMovedTask(event.src_path, event.dest_path)
        QUEUE.put(task)

    def on_deleted(self, event):
        """Put a comic deleted task on the queue."""
        if self.is_ignored(event.is_directory, event.src_path):
            return

        self._wait_for_delete(event.src_path)
        if event.is_directory:
            task = FolderDeletedTask(event.src_path)
        else:
            task = ComicDeletedTask(event.src_path)
        QUEUE.put(task)


class Uatu(Observer):
    """Watch over librarys from the blue area of the moon."""

    def __init__(self, *args, **kwargs):
        """Intialize pk to watches dict."""
        super().__init__(*args, **kwargs)
        self._pk_watches = dict()

    def unwatch_library(self, pk):
        """Stop a watch process."""
        watch = self._pk_watches.pop(pk, None)
        if watch:
            self.unschedule(watch)
            LOG.info(f"Watcher stopped watching library {pk}")
        else:
            LOG.debug(f"library {pk} not being watched")

    def watch_library(self, pk):
        """Start a library watching process."""
        if pk in self._pk_watches:
            LOG.debug(f"library {pk} already being watched.")
            return
        try:
            library = Library.objects.get(pk=pk, enable_watch=True)
        except Library.DoesNotExist as exc:
            LOG.exception(exc)
            return
        path = library.path
        handler = CodexLibraryEventHandler(pk)

        try:
            watch = self.schedule(handler, path, recursive=True)
            self._pk_watches[pk] = watch
            LOG.info(f"Watcher started watching {path}")
        except FileNotFoundError:
            LOG.warn(f"Could not find {path} to watch. May be unmounted.")
            return

    def set_library_watch(self, pk, watch):
        """Watch or unwatch a library."""
        if watch:
            self.watch_library(pk)
        else:
            self.unwatch_library(pk)

    def set_all_library_watches(self):
        """Watch or unwatch all librareis according to the db."""
        rps = (
            Library.objects.all()
            .only("pk", "enable_watch")
            .values("pk", "enable_watch")
        )
        active_watch_pks = set()
        for rp in rps:
            self.set_library_watch(rp.get("pk"), rp.get("enable_watch"))
            active_watch_pks.add(rp.get("pk"))
        missing_watch_pks = set(self._pk_watches.keys()) - active_watch_pks
        for pk in missing_watch_pks:
            self.unwatch_library(pk)

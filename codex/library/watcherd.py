"""Watch file trees for changes."""
import logging
import os
import time

from multiprocessing import Condition
from multiprocessing import Process
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from codex.library.importer import COMIC_MATCHER
from codex.library.queue import QUEUE
from codex.library.queue import ComicDeletedTask
from codex.library.queue import ComicModifiedTask
from codex.library.queue import ComicMovedTask
from codex.library.queue import FolderDeletedTask
from codex.library.queue import FolderMovedTask
from codex.models import RootPath


LOG = logging.getLogger(__name__)


class CodexLibraryEventHandler(FileSystemEventHandler):
    """Handle events for comics in a root path."""

    EVENT_DELAY = 1

    def __init__(self, root_path_id, *args, **kwargs):
        """Let us send along he root path id."""
        self.root_path_id = root_path_id
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
                    stat = full_path.stat()
                    size += stat.st_size
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
        task = ComicModifiedTask(event.src_path, self.root_path_id)
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


class RootPathWatcher:
    """Hold condtions for processs indexed by RootPath pk."""

    WAIT_INTERVAL = 60
    _CONDITIONS = {}

    @classmethod
    def watch(cls, cond, pk, path):
        """Watch a path and log the events."""
        handler = CodexLibraryEventHandler(pk)

        observer = Observer()
        try:
            observer.schedule(handler, path, recursive=True)
        except FileNotFoundError:
            LOG.warn(f"Could not find {path} to watch. May be unmounted.")
            return
        observer.start()
        LOG.info(f"Started watching {path}")

        with cond:
            while True:
                cond.wait(timeout=cls.WAIT_INTERVAL)
                try:
                    root_path = RootPath.objects.get(pk=pk)
                    if not root_path.enable_watch:
                        break
                except RootPath.DoesNotExist:
                    LOG.debug(f"RootPath {pk} doesn't exist.")
                    break

        observer.stop()
        observer.join()
        LOG.info(f"Stopped watching {path}")

    @classmethod
    def start_watch(cls, pk):
        """Start a root path watching process."""
        try:
            root_path = RootPath.objects.get(pk=pk, enable_watch=True)
        except RootPath.DoesNotExist:
            LOG.warn(f"RootPath {pk} with watch enabled doesn't exist.")
            return
        cls.stop_watch(pk)
        cond = Condition()
        name = f"watch-root_path-{pk}"
        proc = Process(
            target=cls.watch, name=name, args=(cond, pk, root_path.path), daemon=True
        )
        cls._CONDITIONS[pk] = cond
        proc.start()

    @classmethod
    def stop_watch(cls, pk):
        """Stop a watch process."""
        cond = cls._CONDITIONS.get(pk)
        if not cond:
            LOG.warning(f"Wake contition not found for Root Path {pk}. Can't stop it.")
            return
        with cond:
            cond.notify()
        del cls._CONDITIONS[pk]

    @classmethod
    def stop_all(cls):
        """Stop all the processes."""
        for pk in cls._CONDITIONS.keys():
            cls.stop_watch(pk)

    @classmethod
    def start_all(cls):
        """Watch all root paths."""
        pks = RootPath.objects.filter(enable_watch=True).values_list("pk", flat=True)
        for pk in pks:
            cls.start_watch(pk)

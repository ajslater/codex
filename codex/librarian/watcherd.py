"""Watch librarys recursively for changes."""
import logging
import os
import time

from pathlib import Path
from queue import Empty

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from codex.buffer_thread import BufferThread, TimedMessage
from codex.librarian.queue_mp import (
    QUEUE,
    BulkComicMovedTask,
    BulkFolderMovedTask,
    ScanRootTask,
)
from codex.librarian.regex import COMIC_MATCHER
from codex.models import Library


LOG = logging.getLogger(__name__)


class CodexLibraryEventHandler(FileSystemEventHandler):
    """Handle watchdog events for comics in a library."""

    EVENT_DELAY = 0.05

    def __init__(self, library_pk, *args, **kwargs):
        """Let us send along he library id."""
        self.library_pk = library_pk
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
        while old_size != cls.get_size(path, is_dir):
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
        message = ScanRootMessage(self.library_pk)
        EventBatchThread.MESSAGE_QUEUE.put(message)

    def on_created(self, event):
        """Do the same thing as for modified."""
        self.on_modified(event)

    def on_moved(self, event):
        """
        Put a comic moved task on the queue.

        Watchdog events can arrive in any order, but often file events
        occur before folder events.
        """
        if self.is_ignored(event.is_directory, event.dest_path):
            return

        self._wait_for_copy(event.dest_path, event.is_directory)
        if event.is_directory:
            message = FolderMovedMessage(
                self.library_pk, event.src_path, event.dest_path
            )
        else:
            message = ComicMovedMessage(
                self.library_pk, event.src_path, event.dest_path
            )
        EventBatchThread.MESSAGE_QUEUE.put(message)

    def on_deleted(self, event):
        """Put a comic deleted task on the queue."""
        if self.is_ignored(event.is_directory, event.src_path):
            return

        self._wait_for_delete(event.src_path)
        message = ScanRootMessage(self.library_pk)
        EventBatchThread.MESSAGE_QUEUE.put(message)


class Uatu(Observer):
    """Watch over librarys from the blue area of the moon."""

    SHUTDOWN_TIMEOUT = 5

    def __init__(self, *args, **kwargs):
        """Intialize pk to watches dict."""
        EventBatchThread.startup()
        super().__init__(*args, **kwargs)
        self._pk_watches = dict()

    def stop(self):
        EventBatchThread.shutdown()
        super().stop()

    def unwatch_library(self, pk):
        """Stop a watch process."""
        watch = self._pk_watches.pop(pk, None)
        if watch:
            self.unschedule(watch)
            LOG.info(f"Stopped watching library {pk}")
        else:
            LOG.debug(f"Library {pk} not being watched")

    def watch_library(self, pk):
        """Start a library watching process."""
        if pk in self._pk_watches:
            LOG.debug(f"Library {pk} already being watched.")
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
            LOG.info(f"Started watching {path}")
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
        """Watch or unwatch all libraries according to the db."""
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

    def unschedule_all(self):
        """Unschedule all watches."""
        super().unschedule_all()
        self._pk_watches = dict()
        LOG.info("Stopped watching all libraries")


class LibraryMessage(TimedMessage):
    def __init__(self, library_id, *args, **kwargs):
        self.library_id = library_id
        super().__init__(*args, **kwargs)


class ScanRootMessage(LibraryMessage):
    pass


class MovedMessage(LibraryMessage):
    def __init__(self, library_id, src_path, dest_path):
        self.src_path = src_path
        self.dest_path = dest_path
        super().__init__(library_id)


class FolderMovedMessage(MovedMessage):
    pass


class ComicMovedMessage(MovedMessage):
    pass


class EventBatchThread(BufferThread):
    """Batch watchdog events into bulk database tasks."""

    NAME = "watchdog-event-batcher"
    BATCH_DELAY = 2
    MAX_BATCH_WAIT_TIME = 30
    MESSAGE_TASK_MAP = {
        FolderMovedMessage: BulkFolderMovedTask,
        ComicMovedMessage: BulkComicMovedTask,
        ScanRootMessage: ScanRootTask,
    }
    TASK_ORDER = (FolderMovedMessage, ComicMovedMessage, ScanRootMessage)

    def __init__(self):
        """Name the thread."""
        self.events = {
            FolderMovedMessage: {},
            ComicMovedMessage: {},
            ScanRootMessage: {},
        }
        super().__init__()

    def run(self):
        LOG.info("Started watcher batch event worker.")
        while True:
            waiting_since = time.time()
            try:
                message = self.MESSAGE_QUEUE.get(timeout=self.BATCH_DELAY)
                if message == self.SHUTDOWN_MSG:
                    break
                LOG.debug(f"Adding {message} to cache.")
                # Aggregate event into bulk tasks
                class_dict = self.events[message.__class__]
                if message.library_id not in class_dict:
                    class_dict[message.library_id] = {}
                if isinstance(message, MovedMessage):
                    class_dict[message.library_id][message.src_path] = message.dest_path

                wait_left = message.time + self.BATCH_DELAY - time.time()
            except Empty:
                wait_left = 0
            wait_break = time.time() - waiting_since > self.MAX_BATCH_WAIT_TIME
            if self.MESSAGE_QUEUE.empty() and not wait_break and wait_left > 0:
                continue
            # Send all tasks
            for message_cls in self.TASK_ORDER:
                library_params = self.events[message_cls]
                for library_id, moved_paths in library_params.items():
                    params = {"library_id": library_id}
                    if message_cls == ScanRootTask:
                        params["force"] = False
                    else:
                        params["moved_paths"] = moved_paths
                    task_cls = self.MESSAGE_TASK_MAP[message_cls]
                    task = task_cls(**params)
                    LOG.debug(f"Sending task: {task}")
                    QUEUE.put(task)
            # reset the event aggregates
            for message_cls in self.events.keys():
                self.events[message_cls] = {}
        LOG.info("Stopped watcher batch event worker.")

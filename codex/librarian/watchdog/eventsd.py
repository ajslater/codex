"""
Batch watchdog events into bulk database tasks.

Watchdog actually starts events as bulk events with the DirSnapshotDiff
but the built-in filesystem event emitters serialize them, so the most
consistent thing is for the DBEmitter to serialize them in the same way
and then re-serialize everything in this batcher and the event Handler
"""
import re

from copy import deepcopy

from watchdog.events import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_MOVED,
    FileCreatedEvent,
    FileDeletedEvent,
    FileSystemEventHandler,
)

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, DBDiffTask, WatchdogEventTask
from codex.settings.logging import get_logger
from codex.settings.settings import MAX_DB_OPS
from codex.threads import AggregateMessageQueuedThread


_COMIC_REGEX = r"\.(cb[zrt]|pdf)$"
COMIC_MATCHER = re.compile(_COMIC_REGEX, re.IGNORECASE)
LOG = get_logger(__name__)


class EventBatcher(AggregateMessageQueuedThread):
    """Batch watchdog events into bulk database tasks."""

    NAME = "WatchdogEventBatcher"
    CLS_SUFFIX = -len("Event")
    DBDIFF_TASK_PARAMS = {
        "library_id": None,
        "dirs_moved": {},
        "files_moved": {},
        "files_modified": set(),
        "files_created": set(),
        "dirs_deleted": set(),
        "dirs_modified": set(),
        "files_deleted": set(),
    }
    MAX_DELAY = 60

    def __init__(self, *args, **kwargs):
        """Set the total items for limiting db ops per batch."""
        super().__init__(*args, **kwargs)
        self._total_items = 0

    def _ensure_library_args(self, library_id):
        if library_id in self.cache:
            return
        args = deepcopy(self.DBDIFF_TASK_PARAMS)
        args["library_id"] = library_id
        self.cache[library_id] = args

    def _args_field_by_event(self, library_id, event):
        """Translate event class names into field names."""
        self._ensure_library_args(library_id)

        if event.is_directory:
            prefix = "dir"
        else:
            prefix = "file"
        field = f"{prefix}s_{event.event_type}"

        args_field = self.cache[library_id].get(field)
        return args_field

    def aggregate_items(self, task):
        """Aggregate events into cache by library."""
        event = task.event
        args_field = self._args_field_by_event(task.library_id, event)
        if args_field is None:
            LOG.debug(f"Unhandled event, not batching: {event}")
            return

        if event.event_type == EVENT_TYPE_MOVED:
            args_field[event.src_path] = event.dest_path
        else:
            args_field.add(event.src_path)
        self._total_items += 1
        if self._total_items > MAX_DB_OPS:
            LOG.info("Event batcher hit max_db_ops limit.")
            # Sends all items
            self.timed_out()

    def _deduplicate_events(self, library_id):
        """Prune different event types on the same paths."""
        args = self.cache[library_id]

        # deleted
        for src_path in args["dirs_deleted"]:
            try:
                del args["dirs_moved"][src_path]
            except KeyError:
                pass
        for src_path in args["files_deleted"]:
            try:
                del args["files_moved"][src_path]
            except KeyError:
                pass
        # created
        args["files_created"] -= args["files_deleted"]
        files_dest_paths = set(args["files_moved"].values())
        args["files_created"] -= files_dest_paths
        # modified
        args["dirs_modified"] -= args["dirs_deleted"]
        args["dirs_modified"] -= set(args["dirs_moved"].values())
        args["files_modified"] -= args["files_created"]
        args["files_modified"] -= args["files_deleted"]
        args["files_modified"] -= files_dest_paths

    def _create_task(self, library_id):
        """Create a task from cached aggregated message data."""
        self._deduplicate_events(library_id)
        args = self.cache[library_id]
        return DBDiffTask(**args)

    def send_all_items(self):
        """Send all tasks to library queue and reset events cache."""
        library_ids = set()
        for library_id in self.cache.keys():
            task = self._create_task(library_id)
            LIBRARIAN_QUEUE.put(task)
            library_ids.add(library_id)

        # reset the event aggregates
        self.cleanup_cache(library_ids)
        self._total_items = 0


class CodexLibraryEventHandler(FileSystemEventHandler):
    """Handle watchdog events for comics in a library."""

    def __init__(self, library, *args, **kwargs):
        """Let us send along he library id."""
        super().__init__(*args, **kwargs)
        self.library_pk = library.pk

    def dispatch(self, event):
        """Send only valid codex events to the EventBatcher."""
        try:
            if event.is_directory:
                if event.event_type == EVENT_TYPE_CREATED:
                    # Directories are only created by comics
                    return
            else:
                source_match = COMIC_MATCHER.search(event.src_path)
                if event.event_type == EVENT_TYPE_MOVED:
                    # Some types of file moves need to be cast as other events.

                    dest_match = COMIC_MATCHER.search(event.dest_path)
                    if source_match is None and dest_match is not None:
                        # Moved from an ignored file extension into a comic type,
                        # so create a new comic.
                        event = FileCreatedEvent(event.dest_path)
                    elif source_match is not None and dest_match is None:
                        # moved into something that's not a comic name so delete
                        event = FileDeletedEvent(event.src_path)
                elif source_match is None:
                    # Don't process non-moved, non-comic files at all
                    return

            task = WatchdogEventTask(self.library_pk, event)
            LIBRARIAN_QUEUE.put(task)
            super().dispatch(event)
        except Exception as exc:
            LOG.error(f"Error in {self.__class__.__name__}")
            LOG.exception(exc)

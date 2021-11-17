"""Batch watchdog events into bulk database tasks."""
from logging import getLogger

from watchdog.events import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_MOVED,
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, DBDiffTask
from codex.librarian.regex import COMIC_MATCHER
from codex.threads import AggregateMessageQueuedThread


LOG = getLogger(__name__)


class EventBatcher(AggregateMessageQueuedThread):
    """Batch watchdog events into bulk database tasks."""

    NAME = "WatchdogEventBatcher"
    EVENT_FIELD_MAP = {
        DirMovedEvent: "dirs_moved",
        FileMovedEvent: "files_moved",
        FileModifiedEvent: "files_modified",
        FileCreatedEvent: "files_created",
        DirDeletedEvent: "dirs_deleted",
        FileDeletedEvent: "files_deleted",
        DirModifiedEvent: "dirs_modified",
    }
    IGNORE_EVENTS = (DirCreatedEvent, DirModifiedEvent)

    def _aggregate_items(self, message):
        """Aggregate events into cache."""
        library_pk, event = message

        if event.__class__ in self.IGNORE_EVENTS:
            return

        if library_pk not in self.cache:
            self.cache[library_pk] = set()
        self.cache[library_pk].add(event)

    def _create_task_from_events(self, library_id, events):
        """Create a task from cached aggregated message data."""
        params = {
            "library_id": library_id,
            "dirs_moved": {},
            "files_moved": {},
            "files_modified": set(),
            "files_created": set(),
            "dirs_deleted": set(),
            "dirs_modified": set(),
            "files_deleted": set(),
        }
        for event in events:
            field = self.EVENT_FIELD_MAP[event.__class__]
            if event.event_type == EVENT_TYPE_MOVED:
                params[field][event.src_path] = event.dest_path
            else:
                params[field].add(event.src_path)

        return DBDiffTask(**params)

    def _send_all_items(self):
        """Send all tasks to library queue and reset events cache."""
        library_ids = set()
        for library_id, events in self.cache.items():
            task = self._create_task_from_events(library_id, events)
            LIBRARIAN_QUEUE.put(task)
            library_ids.add(library_id)

        # reset the event aggregates
        self._cleanup_cache(library_ids)

    @classmethod
    def startup(cls):
        """Start the event batcher."""
        cls.thread = EventBatcher()
        cls.thread.start()


class CodexLibraryEventHandler(FileSystemEventHandler):
    """Handle watchdog events for comics in a library."""

    def __init__(self, library_pk, *args, **kwargs):
        """Let us send along he library id."""
        self.library_pk = library_pk
        super().__init__(*args, **kwargs)

    def dispatch(self, event):
        """Send only valid codex events to the EventBatcher."""
        if event.is_directory:
            if event.event_type == EVENT_TYPE_CREATED:
                # Directories are only created by comics
                return
        else:
            if event.event_type == EVENT_TYPE_MOVED:
                if (
                    COMIC_MATCHER.search(event.src_path) is None
                    and COMIC_MATCHER.search(event.dest_path) is not None
                ):
                    # Moved from an ignored file extension into a comic type,
                    # so create a new comic.
                    event = FileCreatedEvent(event.dest_path)
                # Keep badly renamed comics in the database
                # elif COMIC_MATCHER.search(event.src_path) is not None
                #      and COMIC_MATCHER.search(event.dest_path) is None:
                #    # moved into something that's not a comic name so delete
                #    event = FileDeletedEvent(event.src_path)
            elif COMIC_MATCHER.search(event.src_path) is None:
                # Don't process non comic files at all
                return

        EventBatcher.thread.queue.put((self.library_pk, event))
        super().dispatch(event)

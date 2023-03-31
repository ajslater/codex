"""Watchdog Event Handlers."""
import re

from watchdog.events import (
    EVENT_TYPE_CLOSED,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_MOVED,
    EVENT_TYPE_OPENED,
    FileCreatedEvent,
    FileDeletedEvent,
    FileSystemEventHandler,
)

from codex.librarian.watchdog.tasks import WatchdogEventTask
from codex.logger_base import LoggerBaseMixin

_COMIC_REGEX = r"\.(cb[zrt]|pdf)$"
_COMIC_MATCHER = re.compile(_COMIC_REGEX, re.IGNORECASE)


class CodexLibraryEventHandler(FileSystemEventHandler, LoggerBaseMixin):
    """Handle watchdog events for comics in a library."""

    IGNORED_EVENTS = {EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED}

    def __init__(self, library, *args, **kwargs):
        """Let us send along he library id."""
        self.library_pk = library.pk
        self.librarian_queue = kwargs.pop("librarian_queue")
        log_queue = kwargs.pop("log_queue")
        self.init_logger(log_queue)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _transform_file_event(event):
        """Transform file events into other events."""
        source_match = _COMIC_MATCHER.search(event.src_path)
        if event.event_type == EVENT_TYPE_MOVED:
            # Some types of file moves need to be cast as other events.

            dest_match = _COMIC_MATCHER.search(event.dest_path)
            if source_match is None and dest_match is not None:
                # Moved from an ignored file extension into a comic type,
                # so create a new comic.
                event = FileCreatedEvent(event.dest_path)
            elif source_match is not None and dest_match is None:
                # moved into something that's not a comic name so delete
                event = FileDeletedEvent(event.src_path)
        elif source_match is None:
            # Don't process non-moved, non-comic files at all
            return None
        return event

    @classmethod
    def _transform_event(cls, event):
        """Transform events into other events."""
        if event.event_type in cls.IGNORED_EVENTS:
            event = None
        elif event.is_directory:
            if event.event_type == EVENT_TYPE_CREATED:
                # Directories are only created by comics
                event = None
        else:
            event = cls._transform_file_event(event)
        return event

    def dispatch(self, event):
        """Send only valid codex events to the EventBatcher."""
        try:
            event = self._transform_event(event)
            if not event:
                return

            # Send it to the EventBatcher
            task = WatchdogEventTask(self.library_pk, event)
            self.librarian_queue.put(task)

            # Calls stub event dispatchers
            # super().dispatch(event)
        except Exception:
            self.log.exception(f"{self.__class__.__name__} dispatch")

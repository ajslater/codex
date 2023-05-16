"""Watchdog Event Handlers."""
import re
from os import fsdecode

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


class CodexLibraryEventHandler(FileSystemEventHandler, LoggerBaseMixin):
    """Handle watchdog events for comics in a library."""

    IGNORED_EVENTS = {EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED}

    def __init__(self, library, *args, **kwargs):
        """Let us send along he library id."""
        self.library_pk = library.pk
        self.librarian_queue = kwargs.pop("librarian_queue")
        log_queue = kwargs.pop("log_queue")
        self.init_logger(log_queue)
        unrar = kwargs.pop("unrar", False)
        comic_regex = r"\.(cb[zrt]|pdf)$" if unrar else r"\.(cb[zt]|pdf)$"
        self._comic_matcher = re.compile(comic_regex, re.IGNORECASE)
        super().__init__(*args, **kwargs)

    def _match_comic_suffix(self, path):
        """Match a supported comic suffix."""
        if not path:
            return False
        # We don't care about general suffixes. Only length four.
        suffix = path[-4:]
        suffix = fsdecode(suffix)
        return self._comic_matcher.match(suffix) is not None

    def _transform_file_event(self, event):
        """Transform file events into other events."""
        source_match = self._match_comic_suffix(event.src_path)
        if event.event_type == EVENT_TYPE_MOVED:
            # Some types of file moves need to be cast as other events.
            dest_match = self._match_comic_suffix(event.dest_path)
            if not source_match and dest_match:
                # Moved from an ignored file extension into a comic type,
                # so create a new comic.
                event = FileCreatedEvent(event.dest_path)
            elif source_match and not dest_match:
                # moved into something that's not a comic name so delete
                event = FileDeletedEvent(event.src_path)
        elif not source_match:
            # Don't process non-moved, non-comic files at all
            event = None
        return event

    def _transform_event(self, event):
        """Transform events into other events."""
        if event.event_type in self.IGNORED_EVENTS:
            event = None
        elif event.is_directory:
            if event.event_type == EVENT_TYPE_CREATED:
                # Directories are only created by comics
                event = None
        else:
            event = self._transform_file_event(event)
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

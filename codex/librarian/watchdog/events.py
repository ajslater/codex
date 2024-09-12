"""Watchdog Event Handlers."""

import re
from os import fsdecode
from pathlib import Path
from types import MappingProxyType

from comicbox.box import Comicbox
from watchdog.events import (
    EVENT_TYPE_CLOSED,
    EVENT_TYPE_CLOSED_NO_WRITE,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
    EVENT_TYPE_OPENED,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)

from codex.librarian.watchdog.tasks import WatchdogEventTask
from codex.logger.logging import get_logger
from codex.logger_base import LoggerBaseMixin
from codex.models import CustomCover
from codex.settings.settings import CUSTOM_COVERS_DIR, CUSTOM_COVERS_GROUP_DIRS

LOG = get_logger(__name__)
_IMAGE_EXTS = frozenset({"jpg", "jpeg", "webp", "png", "gif", "bmp"})
_GROUP_COVERS_DIRS = frozenset(CUSTOM_COVERS_GROUP_DIRS)


class CoverMovedEvent(FileMovedEvent):
    """Cover Modified."""

    is_cover = True
    is_synthetic = True


class CoverModifiedEvent(FileModifiedEvent):
    """Cover Modified."""

    is_cover = True
    is_synthetic = True


class CoverCreatedEvent(FileCreatedEvent):
    """Cover Created."""

    is_cover = True
    is_synthetic = True


class CoverDeletedEvent(FileDeletedEvent):
    """Cover Deleted."""

    is_cover = True
    is_synthetic = True


COVERS_EVENT_TYPE_MAP = MappingProxyType(
    {
        EVENT_TYPE_MODIFIED: CoverModifiedEvent,
        EVENT_TYPE_CREATED: CoverCreatedEvent,
        EVENT_TYPE_DELETED: CoverDeletedEvent,
    }
)


class CodexEventHandlerBase(FileSystemEventHandler, LoggerBaseMixin):
    """Base class for Codex Event Handlers."""

    IGNORED_EVENTS = frozenset(
        {EVENT_TYPE_CLOSED, EVENT_TYPE_CLOSED_NO_WRITE, EVENT_TYPE_OPENED}
    )

    def __init__(self, library, *args, **kwargs):
        """Let us send along he library id."""
        self.library_pk = library.pk
        self.librarian_queue = kwargs.pop("librarian_queue")
        log_queue = kwargs.pop("log_queue")
        self.init_logger(log_queue)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _match_image_suffix(path: Path) -> bool:
        return path and len(path.suffix) > 1 and path.suffix[1:] in _IMAGE_EXTS


class CodexLibraryEventHandler(CodexEventHandlerBase):
    """Handle watchdog events for comics in a library."""

    def _set_comic_matcher(self):
        comic_regex = r"\.(cb[zt"
        unsupported = []
        if Comicbox.is_unrar_supported():
            comic_regex += r"r"
        else:
            unsupported.append("CBR")
        comic_regex += r"]"

        if Comicbox.is_pdf_supported():
            comic_regex += r"|pdf"
        else:
            unsupported.append("PDF")
        comic_regex += ")$"
        self._comic_matcher = re.compile(comic_regex, re.IGNORECASE)
        if unsupported:
            un_str = ", ".join(unsupported)
            LOG.warning(f"Cannot detect or read from {un_str} archives")

    def __init__(self, *args, **kwargs):
        """Let us send along he library id."""
        self._set_comic_matcher()
        super().__init__(*args, **kwargs)

    def _match_comic_suffix(self, path):
        """Match a supported comic suffix."""
        if not path:
            return False
        # We don't care about general suffixes. Only length four.
        suffix = path[-4:]
        suffix = fsdecode(suffix)
        return self._comic_matcher.match(suffix) is not None

    @classmethod
    def _match_folder_cover(cls, path_str: str) -> bool:
        if not path_str:
            return False
        path = Path(path_str)
        return path.stem == CustomCover.FOLDER_COVER_STEM and cls._match_image_suffix(
            path
        )

    def _transform_file_move_event(
        self,
        event,
        events,
        source_match_comic,
    ):
        """Create file events for file moves."""
        dest_match_comic = self._match_comic_suffix(event.dest_path)
        if not source_match_comic and dest_match_comic:
            # Moved from an ignored file extension into a comic type,
            # so create a new comic.
            events.append(FileCreatedEvent(event.dest_path))
        elif source_match_comic and not dest_match_comic:
            # moved into something that's not a comic name so delete
            events.append(FileDeletedEvent(event.src_path))
        elif source_match_comic and dest_match_comic:
            events.append(event)

    def _transform_file_move_event_to_cover_event(self, event, events):
        """Create cover events for file moves."""
        source_match_cover = self._match_folder_cover(event.src_path)
        dest_match_cover = self._match_folder_cover(event.dest_path)
        if source_match_cover and not dest_match_cover:
            events.append(CoverDeletedEvent(event.src_path))
        elif not source_match_cover and dest_match_cover:
            events.append(CoverCreatedEvent(event.dest_path))
        elif source_match_cover and dest_match_cover:
            events.append(CoverMovedEvent(event.src_path, event.dest_path))

    def _transform_file_event(self, event):
        """Transform file events into other events."""
        events = []
        source_match_comic = self._match_comic_suffix(event.src_path)
        if event.event_type == EVENT_TYPE_MOVED:
            self._transform_file_move_event(event, events, source_match_comic)
            self._transform_file_move_event_to_cover_event(event, events)
        elif source_match_comic:
            events.append(event)
        else:
            source_match_cover = self._match_folder_cover(event.src_path)
            if source_match_cover and (
                event_class := COVERS_EVENT_TYPE_MAP.get(event.event_type)
            ):
                # Convert to cover type
                event = event_class(event.src_path)
                events.append(event)
        return events

    def dispatch(self, event):
        """Send only valid codex events to the EventBatcher."""
        try:
            if event.event_type in self.IGNORED_EVENTS or (
                event.is_directory and event.event_type == EVENT_TYPE_CREATED
            ):
                # Directories are only created by comics
                return

            events = self._transform_file_event(event)

            # Send it to the EventBatcher
            for sub_event in events:
                task = WatchdogEventTask(self.library_pk, sub_event)
                self.librarian_queue.put(task)

            # Calls stub event dispatchers
            # super().dispatch(event)
        except Exception:
            self.log.exception(f"{self.__class__.__name__} dispatch")


class CodexCustomCoverEventHandler(CodexEventHandlerBase):
    """Special event handler for the custom cover dir."""

    @classmethod
    def _match_group_cover_image(cls, path_str: str) -> bool:
        path = Path(path_str)
        parent = path.parent
        if (
            parent.parent != CUSTOM_COVERS_DIR
            or str(parent.name) not in _GROUP_COVERS_DIRS
        ):
            return False
        return cls._match_image_suffix(path)

    @classmethod
    def _transform_event_moved(cls, event, src_cover_match):
        """Get a cover event for a file moved event."""
        send_event = None
        dest_cover_match = cls._match_group_cover_image(event.dest_path)
        if src_cover_match and dest_cover_match:
            send_event = CoverMovedEvent(event.src_path, event.dest_path)
        elif not src_cover_match and dest_cover_match:
            send_event = CoverCreatedEvent(event.dest_path)
        elif src_cover_match and not dest_cover_match:
            send_event = CoverDeletedEvent(event.src_path)
        return send_event

    def dispatch(self, event):
        """Send only valid cover events to the EventBatcher."""
        send_event = None
        try:
            if event.is_directory or event.event_type in self.IGNORED_EVENTS:
                return
            src_cover_match = self._match_group_cover_image(str(event.src_path))
            if event.event_type == EVENT_TYPE_MOVED:
                send_event = self._transform_event_moved(event, src_cover_match)
            elif src_cover_match:
                event_class = COVERS_EVENT_TYPE_MAP.get(event.event_type)
                if not event_class:
                    return
                send_event = event_class(event.src_path)

            if send_event:
                task = WatchdogEventTask(self.library_pk, send_event)
                self.librarian_queue.put(task)
        except Exception:
            self.log.exception(f"{self.__class__.__name__} dispatch")

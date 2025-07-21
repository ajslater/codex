"""Watchdog Event Handlers."""

from abc import ABC, abstractmethod
from multiprocessing import Queue
from os import fsdecode
from pathlib import Path

from typing_extensions import override
from watchdog.events import (
    EVENT_TYPE_MOVED,
    FileCreatedEvent,
    FileDeletedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)

from codex.librarian.watchdog.const import COMIC_MATCHER, COVERS_EVENT_TYPE_MAP
from codex.librarian.watchdog.events import (
    CodexPollEvent,
    CoverCreatedEvent,
    CoverDeletedEvent,
    CoverMovedEvent,
)
from codex.librarian.watchdog.tasks import WatchdogEventTask
from codex.librarian.worker import WorkerMixin
from codex.models import CustomCover
from codex.settings import CUSTOM_COVERS_DIR, CUSTOM_COVERS_GROUP_DIRS

_IMAGE_EXTS = frozenset({"jpg", "jpeg", "webp", "png", "gif", "bmp"})
_GROUP_COVERS_DIRS = frozenset(CUSTOM_COVERS_GROUP_DIRS)


class CodexEventHandlerBase(WorkerMixin, FileSystemEventHandler, ABC):
    """Base class for Codex Event Handlers."""

    def __init__(
        self,
        library_pk: int,
        *args,
        logger_,
        librarian_queue: Queue,
        db_write_lock,
        **kwargs,
    ):
        """Let us send along he library id."""
        self.library_pk = library_pk
        self.init_worker(logger_, librarian_queue, db_write_lock)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _match_image_suffix(path: Path) -> bool:
        return bool(path and path.suffix[1:] in _IMAGE_EXTS)

    @classmethod
    @abstractmethod
    def transform_file_event(
        cls, event: FileSystemEvent
    ) -> tuple[FileSystemEvent, ...]:
        """Transform events into valid cover events."""
        raise NotImplementedError

    @override
    def dispatch(self, event):
        """Send only valid codex events to the EventBatcher."""
        try:
            if isinstance(event, CodexPollEvent):
                events = [event]
            else:
                events = self.transform_file_event(event)

            # Send it to the EventBatcher
            for sub_event in events:
                task = WatchdogEventTask(self.library_pk, sub_event)
                self.librarian_queue.put(task)

            # Do not call super dispatch to call stub event dispatchers
        except Exception:
            self.log.exception(f"{self.__class__.__name__} dispatch")


class CodexLibraryEventHandler(CodexEventHandlerBase):
    """Handle watchdog events for comics in a library."""

    @staticmethod
    def _match_comic_suffix(path):
        """Match a supported comic suffix."""
        if not path:
            return False
        # We don't care about general suffixes. Only length four.
        suffix = path[-4:]
        suffix = fsdecode(suffix)
        return COMIC_MATCHER.match(suffix) is not None

    @classmethod
    def _match_folder_cover(cls, path_str: str | bytes) -> bool:
        if not path_str:
            return False
        if isinstance(path_str, bytes):
            path_str = path_str.decode()
        path = Path(path_str)
        return path.stem == CustomCover.FOLDER_COVER_STEM and cls._match_image_suffix(
            path
        )

    @classmethod
    def _transform_file_move_event(
        cls,
        event,
        events,
        source_match_comic,
    ):
        """Create file events for file moves."""
        dest_match_comic = cls._match_comic_suffix(event.dest_path)
        if not source_match_comic and dest_match_comic:
            # Moved from an ignored file extension into a comic type,
            # so create a new comic.
            events.append(FileCreatedEvent(event.dest_path))
        elif source_match_comic and not dest_match_comic:
            # moved into something that's not a comic name so delete
            events.append(FileDeletedEvent(event.src_path))
        elif source_match_comic and dest_match_comic:
            events.append(event)

    @classmethod
    def _transform_file_move_event_to_cover_event(cls, event, events):
        """Create cover events for file moves."""
        source_match_cover = cls._match_folder_cover(event.src_path)
        dest_match_cover = cls._match_folder_cover(event.dest_path)
        if source_match_cover and not dest_match_cover:
            events.append(CoverDeletedEvent(event.src_path))
        elif not source_match_cover and dest_match_cover:
            events.append(CoverCreatedEvent(event.dest_path))
        elif source_match_cover and dest_match_cover:
            events.append(CoverMovedEvent(event.src_path, event.dest_path))

    @override
    @classmethod
    def transform_file_event(cls, event: FileSystemEvent) -> tuple[FileSystemEvent]:
        """Transform file events into other events."""
        events = []
        source_match_comic = cls._match_comic_suffix(event.src_path)
        if event.event_type == EVENT_TYPE_MOVED:
            cls._transform_file_move_event(event, events, source_match_comic)
            cls._transform_file_move_event_to_cover_event(event, events)
        elif source_match_comic:
            events.append(event)
        else:
            source_match_cover = cls._match_folder_cover(event.src_path)
            if source_match_cover and (
                event_class := COVERS_EVENT_TYPE_MAP.get(event.event_type)
            ):
                # Convert to cover type
                event = event_class(event.src_path)
                events.append(event)
        return tuple(events)


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

    @override
    @classmethod
    def transform_file_event(
        cls, event: FileSystemEvent
    ) -> tuple[FileSystemEvent, ...]:
        """Transform events into valid cover events."""
        send_events = []
        if event.is_directory:
            return tuple(send_events)
        src_cover_match = cls._match_group_cover_image(str(event.src_path))
        if event.event_type == EVENT_TYPE_MOVED:
            if send_event := cls._transform_event_moved(event, src_cover_match):
                send_events.append(send_event)
        elif src_cover_match and (
            event_class := COVERS_EVENT_TYPE_MAP.get(event.event_type)
        ):
            send_event = event_class(event.src_path)
            send_events.append(send_event)
        return tuple(send_events)

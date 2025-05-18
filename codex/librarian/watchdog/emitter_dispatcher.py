"""Dispatch an Importer Task from an diff without serializing back into the queue."""

from collections.abc import Generator
from itertools import chain
from multiprocessing.queues import Queue
from pathlib import Path
from threading import Condition
from types import MappingProxyType

from watchdog.events import (
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
)
from watchdog.observers.api import (
    DEFAULT_EMITTER_TIMEOUT,
    EventEmitter,
    EventQueue,
    ObservedWatch,
)
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff

from codex.librarian.importer.tasks import ImportDBDiffTask
from codex.librarian.watchdog.const import (
    EVENT_CLASS_DIFF_ALL_MAP,
    EVENT_CLASS_DIFF_ATTR_MAP,
    EVENT_COVERS_DIFF_ATTR_MAP,
    EVENT_COVERS_MOVED_CLASS_DIFF_ATTR_MAP,
    EVENT_MOVED_CLASS_DIFF_ATTR_MAP,
)
from codex.librarian.watchdog.event_aggregator import EventAggregatorMixin
from codex.librarian.watchdog.handlers import (
    CodexCustomCoverEventHandler,
    CodexLibraryEventHandler,
)
from codex.librarian.worker import WorkerStatusMixin

_CODEX_EVENT_FILTER: list[type[FileSystemEvent]] = [
    FileMovedEvent,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    # FileClosedEvent,
    # FileOpenedEvent,
    DirMovedEvent,
    DirModifiedEvent,
    DirDeletedEvent,
    # DirCreatedEvent,
]
_DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"


class DatabasePollingEmitterDispatcher(
    EventEmitter, WorkerStatusMixin, EventAggregatorMixin
):
    """Dispatch an Importer Task from an diff without serializing back into the queue."""

    def __init__(  # noqa: PLR0913
        self,
        event_queue: EventQueue,
        watch: ObservedWatch,
        *,
        timeout: float = DEFAULT_EMITTER_TIMEOUT,
        logger_=None,
        librarian_queue: Queue | None = None,
        covers_only=False,
        library_id: int,
    ):
        """Initialize snapshot methods."""
        self.init_worker(logger_, librarian_queue)
        self._poll_cond = Condition()
        self._force = False
        self._watch_path = Path(watch.path)
        self._watch_path_unmounted = self._watch_path / _DOCKER_UNMOUNTED_FN
        self._covers_only = covers_only
        self._handler = (
            CodexCustomCoverEventHandler if covers_only else CodexLibraryEventHandler
        )
        self._library_id = library_id
        super().__init__(
            event_queue, watch, timeout=timeout, event_filter=_CODEX_EVENT_FILTER
        )

        self._take_dir_snapshot = lambda: DirectorySnapshot(
            self._watch.path,
            recursive=self.watch.is_recursive,
            # default stat and listdir params
        )

    def _transform_events(
        self, event_class: type[FileSystemEvent], paths: list[str | bytes]
    ) -> Generator[tuple[FileSystemEvent, ...]]:
        yield from (
            self._handler.transform_file_event(event_class(src_path))
            for src_path in paths
        )

    def _transform_events_moved(
        self,
        event_class: type[FileSystemEvent],
        paths: list[tuple[str | bytes, str | bytes]],
    ) -> Generator[tuple[FileSystemEvent, ...]]:
        yield from (
            self._handler.transform_file_event(event_class(src_path, dest_path))
            for src_path, dest_path in paths
        )

    def _transform_events_group(
        self, diff, class_attr_map: MappingProxyType, args: dict, *, moved: bool
    ):
        transform_func = (
            self._transform_events_moved if moved else self._transform_events
        )
        events = chain.from_iterable(
            chain.from_iterable(
                transform_func(event_class, getattr(diff, attr))
                for event_class, attr in class_attr_map.items()
            )
        )
        if moved:
            for event in events:
                key = EVENT_CLASS_DIFF_ALL_MAP[type(event)]
                args[key][event.src_path] = event.dest_path
        else:
            for event in events:
                key = EVENT_CLASS_DIFF_ALL_MAP[type(event)]
                args[key].add(event.src_path)

    def _build_import_task_args(self, diff: DirectorySnapshotDiff):
        args = self.create_import_task_args(self._library_id)
        if self._covers_only:
            self._transform_events_group(
                diff, EVENT_COVERS_DIFF_ATTR_MAP, args, moved=False
            )
            self._transform_events_group(
                diff, EVENT_COVERS_MOVED_CLASS_DIFF_ATTR_MAP, args, moved=True
            )
        else:
            self._transform_events_group(
                diff, EVENT_CLASS_DIFF_ATTR_MAP, args, moved=False
            )
            self._transform_events_group(
                diff, EVENT_MOVED_CLASS_DIFF_ATTR_MAP, args, moved=True
            )

        self.deduplicate_events(args)

        args["check_metadata_mtime"] = not self._force
        return args

    def dispatch_import_task(self, diff: DirectorySnapshotDiff):
        """Create an import task from the diff."""
        args = self._build_import_task_args(diff)
        task = ImportDBDiffTask(**args)
        if self._covers_only:
            reason = (
                f"Poller sending custom comic covers: {len(task.covers_deleted)} "
                f"deleted, {len(task.covers_modified)} modified, "
                f"{len(task.covers_created)} created, "
                f"{len(task.covers_moved)} moved."
            )
        else:
            reason = (
                f"Poller sending comics: {len(task.files_deleted)} "
                f"deleted, {len(task.files_modified)} modified, "
                f"{len(task.files_created)} created, "
                f"{len(task.files_moved)} moved; "
                f"folders: {len(task.dirs_deleted)} deleted,"
                f" {len(task.dirs_modified)} modified,"
                f" {len(task.dirs_moved)} moved."
            )
        self.log.debug(reason)
        self.librarian_queue.put(task)

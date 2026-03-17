"""
Batch filesystem events into bulk database import tasks.

Events from both the watchfiles watcher and the database poller are
aggregated here by library, deduplicated, and sent to the importer as
ImportTask instances.
"""

from contextlib import suppress
from copy import deepcopy
from types import MappingProxyType

from typing_extensions import override

from codex.librarian.memory import get_mem_limit
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.threads import AggregateMessageQueuedThread
from codex.librarian.watcher.events import (
    WatcherChange,
    WatchEvent,
)
from codex.librarian.watcher.poller.events import (
    PollEvent,
    PollEventType,
)

_IMPORT_TASK_PARAMS: MappingProxyType[str, int | set[int] | dict[str, str]] = (
    MappingProxyType(
        {
            "dirs_moved": {},
            "dirs_modified": set(),
            "dirs_deleted": set(),
            "files_moved": {},
            "files_modified": set(),
            "files_added": set(),
            "files_deleted": set(),
            "covers_moved": {},
            "covers_modified": set(),
            "covers_added": set(),
            "covers_deleted": set(),
        }
    )
)


class WatcherEventBatcherThread(AggregateMessageQueuedThread):
    """Batch filesystem events into bulk database import tasks."""

    MAX_DELAY = 60.0
    MAX_ITEMS_PER_GB = 50000

    @staticmethod
    def create_import_task_args(library_id: int) -> dict:
        """Create import task args."""
        args = deepcopy(dict(_IMPORT_TASK_PARAMS))
        args["library_id"] = library_id
        return args

    @staticmethod
    def _remove_paths(args, deleted_key: str, moved_key: str) -> None:
        for src_path in args[deleted_key]:
            with suppress(KeyError):
                del args[moved_key][src_path]

    @classmethod
    def deduplicate_events(cls, args: dict) -> None:
        """Prune different event types on the same paths."""
        # deleted
        cls._remove_paths(args, "dirs_deleted", "dirs_moved")
        cls._remove_paths(args, "files_deleted", "files_moved")

        # added
        args["files_added"] -= args["files_deleted"]
        files_dest_paths = set(args["files_moved"].values())
        args["files_added"] -= files_dest_paths

        # modified
        args["dirs_modified"] -= args["dirs_deleted"]
        args["dirs_modified"] -= set(args["dirs_moved"].values())

        args["files_modified"] -= args["files_added"]
        args["files_modified"] -= args["files_deleted"]
        args["files_modified"] -= files_dest_paths

        args["covers_modified"] -= args["covers_deleted"]
        args["covers_modified"] -= args["covers_added"]

    def __init__(self, *args, **kwargs) -> None:
        """Set the total items for limiting db ops per batch."""
        super().__init__(*args, **kwargs)
        self._total_items = 0
        mem_limit_gb = get_mem_limit("g")
        self.max_items = int(self.MAX_ITEMS_PER_GB * mem_limit_gb)

    def _args_field_by_event(self, library_id: int, event: WatchEvent):
        """Translate an event into the corresponding import task field."""
        if library_id not in self.cache:
            self.cache[library_id] = self.create_import_task_args(library_id)
        key = event.diff_key
        args_field = self.cache[library_id].get(key)
        if args_field is None:
            reason = f"Unhandled event, not batching: {event}"
            raise ValueError(reason)
        return args_field

    @override
    def aggregate_items(self, item) -> None:
        """Aggregate events into cache by library."""
        event = item.event
        try:
            args_field = self._args_field_by_event(item.library_id, event)
            if event.change == WatcherChange.moved:
                args_field[event.src_path] = event.dest_path
            else:
                args_field.add(event.src_path)
            self._total_items += 1
        except ValueError as exc:
            self.log.debug(exc)
        if self._total_items > self.max_items:
            reason = (
                "Event batcher hit size limit."
                f" Sending batch of {self._total_items} to importer."
            )
            self.log.info(reason)
            self.timed_out()

    def _set_check_metadata_mtime(self, item) -> None:
        pk = item.library_id
        if pk not in self.cache:
            self.cache[pk] = self.create_import_task_args(pk)
        poll_event: PollEvent = item.event
        self.cache[pk]["check_metadata_mtime"] = not poll_event.force

    def _start_poll(self, item) -> None:
        self.set_last_send()
        self._set_check_metadata_mtime(item)

    def _finish_poll(self, item) -> None:
        self._set_check_metadata_mtime(item)
        self.send_all_items()

    @override
    def process_item(self, item) -> None:
        event = item.event
        if isinstance(event, PollEvent):
            if event.poll_type == PollEventType.start:
                self._start_poll(item)
            elif event.poll_type == PollEventType.finish:
                self._finish_poll(item)
        else:
            super().process_item(item)

    def _subtract_args_items(self, args) -> None:
        total = 0
        for value in args.values():
            with suppress(TypeError):
                total += len(value)
        self._total_items = max(0, self._total_items - total)

    def _create_task(self, library_id) -> ImportTask:
        """Create a task from cached aggregated message data."""
        args = self.cache.pop(library_id)
        self._subtract_args_items(args)
        self.deduplicate_events(args)
        args["files_created"] = args.pop("files_added")
        args["covers_created"] = args.pop("covers_added")
        return ImportTask(**args)

    def _send_import_task(self, library_id: int) -> None:
        task = self._create_task(library_id)
        if task.total():
            self.librarian_queue.put(task)
        else:
            self.log.debug("Empty task after filtering. Not sending to importer.")

    @override
    def send_all_items(self) -> None:
        """Send all tasks to library queue and reset events cache."""
        for library_id in tuple(self.cache):
            self._send_import_task(library_id)

        # reset the event aggregates
        self._total_items = 0

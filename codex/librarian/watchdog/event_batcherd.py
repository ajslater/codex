"""
Batch watchdog events into bulk database tasks.

Watchdog actually starts events as bulk events with the DirSnapshotDiff
but the built-in filesystem event emitters serialize them, so the most
consistent thing is for the DBEmitter to serialize them in the same way
and then re-serialize everything in this batcher and the event Handler
"""

from contextlib import suppress
from copy import deepcopy
from types import MappingProxyType

from typing_extensions import override
from watchdog.events import EVENT_TYPE_MOVED, FileSystemEvent

from codex.librarian.memory import get_mem_limit
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.threads import AggregateMessageQueuedThread
from codex.librarian.watchdog.const import EVENT_CLASS_DIFF_ALL_MAP
from codex.librarian.watchdog.events import (
    EVENT_TYPE_FINISH_POLL,
    EVENT_TYPE_START_POLL,
)

_IMPORT_TASK_PARAMS = MappingProxyType(
    {
        "dirs_moved": {},
        "dirs_modified": set(),
        "dirs_deleted": set(),
        "files_moved": {},
        "files_modified": set(),
        "files_created": set(),
        "files_deleted": set(),
        "covers_moved": {},
        "covers_modified": set(),
        "covers_created": set(),
        "covers_deleted": set(),
    }
)


class WatchdogEventBatcherThread(AggregateMessageQueuedThread):
    """Batch watchdog events into bulk database tasks."""

    MAX_DELAY = 60.0
    MAX_ITEMS_PER_GB = 50000

    @staticmethod
    def create_import_task_args(library_id: int) -> dict:
        """Create import task args."""
        args = deepcopy(dict(_IMPORT_TASK_PARAMS))
        args["library_id"] = library_id  # pyright: ignore[reportArgumentType]
        return args

    @staticmethod
    def key_for_event(event: FileSystemEvent) -> str:
        """Return the args field name for the event."""
        return EVENT_CLASS_DIFF_ALL_MAP[type(event)]

    @staticmethod
    def _remove_paths(args, deleted_key: str, moved_key: str):
        for src_path in args[deleted_key]:
            with suppress(KeyError):
                del args[moved_key][src_path]

    @classmethod
    def deduplicate_events(cls, args: dict):
        """Prune different event types on the same paths."""
        # deleted
        cls._remove_paths(args, "dirs_deleted", "dirs_moved")
        cls._remove_paths(args, "files_deleted", "files_moved")

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

        args["covers_modified"] -= args["covers_deleted"]
        args["covers_modified"] -= args["covers_created"]

    def __init__(self, *args, **kwargs):
        """Set the total items for limiting db ops per batch."""
        super().__init__(*args, **kwargs)
        self._total_items = 0
        mem_limit_gb = get_mem_limit("g")
        self.max_items = int(self.MAX_ITEMS_PER_GB * mem_limit_gb)

    def _args_field_by_event(self, library_id: int, event: FileSystemEvent):
        """Translate event class names into field names."""
        if library_id not in self.cache:
            self.cache[library_id] = self.create_import_task_args(library_id)
        if key := EVENT_CLASS_DIFF_ALL_MAP.get(type(event)):
            args_field = self.cache[library_id].get(key)
        else:
            reason = f"Unhandled event, not batching: {event}"
            raise ValueError(reason)
        return args_field

    @override
    def aggregate_items(self, item):
        """Aggregate events into cache by library."""
        event = item.event
        try:
            args_field = self._args_field_by_event(item.library_id, event)
            if event.event_type == EVENT_TYPE_MOVED:
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
            # Send all items
            self.timed_out()

    def _set_check_metadata_mtime(self, item):
        pk = item.library_id
        if pk not in self.cache:
            self.cache[pk] = self.create_import_task_args(pk)
        self.cache[pk]["check_metadata_mtime"] = not item.event.force

    def _start_poll(self, item):
        self.set_last_send()
        self._set_check_metadata_mtime(item)

    def _finish_poll(self, item):
        self._set_check_metadata_mtime(item)
        self.send_all_items()

    @override
    def process_item(self, item):
        event_type = item.event.event_type
        if event_type == EVENT_TYPE_START_POLL:
            self._start_poll(item)
        elif event_type == EVENT_TYPE_FINISH_POLL:
            self._finish_poll(item)
        else:
            super().process_item(item)

    def _subtract_args_items(self, args):
        total = 0
        for value in args.values():
            with suppress(TypeError):
                total += len(value)
        self._total_items = max(0, self._total_items - total)

    def _create_task(self, library_id):
        """Create a task from cached aggregated message data."""
        args = self.cache.pop(library_id)
        self._subtract_args_items(args)
        self.deduplicate_events(args)
        return ImportTask(**args)

    def _send_import_task(self, library_id: int):
        task = self._create_task(library_id)
        if task.total():
            self.librarian_queue.put(task)
        else:
            self.log.debug("Empty task after filtering. Not sending to importer.")

    @override
    def send_all_items(self):
        """Send all tasks to library queue and reset events cache."""
        for library_id in tuple(self.cache):
            self._send_import_task(library_id)

        # reset the event aggregates
        self._total_items = 0

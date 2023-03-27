"""Batch watchdog events into bulk database tasks.

Watchdog actually starts events as bulk events with the DirSnapshotDiff
but the built-in filesystem event emitters serialize them, so the most
consistent thing is for the DBEmitter to serialize them in the same way
and then re-serialize everything in this batcher and the event Handler
"""
from contextlib import suppress
from copy import deepcopy

from watchdog.events import EVENT_TYPE_MOVED

from codex.librarian.importer.tasks import UpdaterDBDiffTask
from codex.memory import get_mem_limit
from codex.threads import AggregateMessageQueuedThread


class WatchdogEventBatcherThread(AggregateMessageQueuedThread):
    """Batch watchdog events into bulk database tasks."""

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
    MAX_ITEMS_PER_GB = 50000

    def __init__(self, *args, **kwargs):
        """Set the total items for limiting db ops per batch."""
        super().__init__(*args, **kwargs)
        self._total_items = 0
        mem_limit_gb = get_mem_limit("g")
        self.max_items = int(self.MAX_ITEMS_PER_GB * mem_limit_gb)

    def _ensure_library_args(self, library_id):
        if library_id in self.cache:
            return
        args = deepcopy(self.DBDIFF_TASK_PARAMS)
        args["library_id"] = library_id
        self.cache[library_id] = args

    def _args_field_by_event(self, library_id, event):
        """Translate event class names into field names."""
        self._ensure_library_args(library_id)

        prefix = "dir" if event.is_directory else "file"
        field = f"{prefix}s_{event.event_type}"

        return self.cache[library_id].get(field)

    def aggregate_items(self, task):
        """Aggregate events into cache by library."""
        event = task.event
        args_field = self._args_field_by_event(task.library_id, event)
        if args_field is None:
            self.log.debug(f"Unhandled event, not batching: {event}")
            return
        if event.event_type == EVENT_TYPE_MOVED:
            args_field[event.src_path] = event.dest_path
        else:
            args_field.add(event.src_path)
        self._total_items += 1
        if self._total_items > self.max_items:
            self.log.info(
                "Event batcher hit size limit."
                f" Sending batch of {self._total_items} to importer."
            )
            # Seall items
            self.timed_out()

    def _deduplicate_events(self, library_id):
        """Prune different event types on the same paths."""
        args = self.cache[library_id]

        # deleted
        for src_path in args["dirs_deleted"]:
            with suppress(KeyError):
                del args["dirs_moved"][src_path]
        for src_path in args["files_deleted"]:
            with suppress(KeyError):
                del args["files_moved"][src_path]
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
        return UpdaterDBDiffTask(**args)

    def send_all_items(self):
        """Send all tasks to library queue and reset events cache."""
        library_ids = set()
        for library_id in self.cache:
            task = self._create_task(library_id)
            self.librarian_queue.put(task)
            library_ids.add(library_id)

        # reset the event aggregates
        self.cleanup_cache(library_ids)
        self._total_items = 0

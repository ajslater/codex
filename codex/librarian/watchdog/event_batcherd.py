"""
Batch watchdog events into bulk database tasks.

Watchdog actually starts events as bulk events with the DirSnapshotDiff
but the built-in filesystem event emitters serialize them, so the most
consistent thing is for the DBEmitter to serialize them in the same way
and then re-serialize everything in this batcher and the event Handler
"""

from typing_extensions import override
from watchdog.events import EVENT_TYPE_MOVED

from codex.librarian.importer.tasks import ImportDBDiffTask
from codex.librarian.threads import AggregateMessageQueuedThread
from codex.librarian.watchdog.event_aggregator import EventAggregatorMixin
from codex.librarian.watchdog.memory import get_mem_limit


class WatchdogEventBatcherThread(AggregateMessageQueuedThread, EventAggregatorMixin):
    """Batch watchdog events into bulk database tasks."""

    MAX_DELAY = 60.0
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
        self.cache[library_id] = self.create_import_task_args(library_id)

    def _args_field_by_event(self, library_id, event):
        """Translate event class names into field names."""
        self._ensure_library_args(library_id)
        key = self.key_for_event(event)
        return self.cache[library_id].get(key)

    @override
    def aggregate_items(self, item):
        """Aggregate events into cache by library."""
        event = item.event
        args_field = self._args_field_by_event(item.library_id, event)
        if args_field is None:
            self.log.debug(f"Unhandled event, not batching: {event}")
            return
        if event.event_type == EVENT_TYPE_MOVED:
            args_field[event.src_path] = event.dest_path
        else:
            args_field.add(event.src_path)
        self._total_items += 1
        if self._total_items > self.max_items:
            reason = (
                "Event batcher hit size limit."
                f" Sending batch of {self._total_items} to importer."
            )
            self.log.info(reason)
            # Send all items
            self.timed_out()

    def _create_task(self, library_id):
        """Create a task from cached aggregated message data."""
        args = self.cache[library_id]
        self.deduplicate_events(args)
        return ImportDBDiffTask(**args)

    @override
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

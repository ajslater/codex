"""Delay tasks."""
from time import sleep

from codex.threads import QueuedThread


class DelayedTasksThread(QueuedThread):
    """Wait for the something before running tasks."""

    NAME = "DelayedTask"  # type: ignore

    def process_item(self, item):
        """Sleep and then put tasks on the queue."""
        sleep(item.delay)
        for task in item.tasks:
            self.librarian_queue.put(task)

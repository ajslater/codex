"""Delay tasks."""

from queue import PriorityQueue
from time import sleep, time

from codex.threads import QueuedThread


class DelayedTasksThread(QueuedThread):
    """Wait for the something before running tasks."""

    def __init__(self, *args, **kwargs):
        """Use a priority queue."""
        super().__init__(*args, queue=PriorityQueue(), **kwargs)

    def process_item(self, item):
        """Sleep and then put tasks on the queue."""
        delay = max(0.0, item.until - time())
        sleep(delay)
        for task in item.tasks:
            self.librarian_queue.put(task)

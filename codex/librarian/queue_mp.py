"""Library SimpleQueue and task definitions."""
# This file cannot be named queue or it causes weird type checker errors
from dataclasses import dataclass
from multiprocessing import Queue


@dataclass
class DelayedTasks:
    """A list of tasks to start on a delay."""

    delay: int
    tasks: tuple


LIBRARIAN_QUEUE = Queue()

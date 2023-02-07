"""Library SimpleQueue and task definitions."""
# This file cannot be named queue or it causes weird type checker errors
from dataclasses import dataclass
from multiprocessing import Queue


# TODO move to tasks
@dataclass
class DelayedTasks:
    """A list of tasks to start on a delay."""

    delay: int
    tasks: tuple


# TODO move to Librarian.QUEUE
LIBRARIAN_QUEUE = Queue()

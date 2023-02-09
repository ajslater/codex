"""Tasks."""
from dataclasses import dataclass


@dataclass
class DelayedTasks:
    """A list of tasks to start on a delay."""

    delay: int
    tasks: tuple

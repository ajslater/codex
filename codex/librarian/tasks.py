"""Tasks."""
from dataclasses import dataclass


@dataclass
class DelayedTasks:
    """A list of tasks to start on a delay."""

    until: float
    tasks: tuple

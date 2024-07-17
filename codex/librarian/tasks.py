"""Librarian Tasks."""

from dataclasses import dataclass, field


@dataclass(order=True)
class DelayedTasks:
    """A list of tasks to start on a delay."""

    until: float
    tasks: tuple = field(compare=False)


class LibrarianShutdownTask:
    """Signal task."""


class WakeCronTask:
    """Signal task."""

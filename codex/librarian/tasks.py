"""Librarian Tasks."""

from abc import ABC


class LibrarianTask(ABC):  # noqa: B024
    """Generic Librarian Task."""


class LibrarianShutdownTask(LibrarianTask):
    """Signal task."""


class WakeCronTask(LibrarianTask):
    """Signal task."""

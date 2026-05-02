"""Filesystem Tasks."""

from dataclasses import dataclass

from codex.librarian.tasks import LibrarianTask


@dataclass
class FSTask(LibrarianTask):
    """Filesystem tasks."""

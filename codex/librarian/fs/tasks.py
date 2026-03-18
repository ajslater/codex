"""Filesystem Tasks."""

from dataclasses import dataclass

from codex.librarian.fs.events import FSEvent
from codex.librarian.fs.poller.events import PollEvent
from codex.librarian.tasks import LibrarianTask


@dataclass
class FSTask(LibrarianTask):
    """Filesystem tasks."""


@dataclass
class FSEventTask(FSTask):
    """Task for filesystem events and poll start and stop events."""

    library_id: int
    event: FSEvent | PollEvent

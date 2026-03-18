"""Watcher Statii."""

from abc import ABC

from codex.librarian.status import Status


class FSStatus(Status, ABC):
    """File System Statii."""

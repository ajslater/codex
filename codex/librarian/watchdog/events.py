"""Codex Filesystem Events."""

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)


class CoverMovedEvent(FileMovedEvent):
    """Cover Modified."""

    is_cover = True
    is_synthetic = True


class CoverModifiedEvent(FileModifiedEvent):
    """Cover Modified."""

    is_cover = True
    is_synthetic = True


class CoverCreatedEvent(FileCreatedEvent):
    """Cover Created."""

    is_cover = True
    is_synthetic = True


class CoverDeletedEvent(FileDeletedEvent):
    """Cover Deleted."""

    is_cover = True
    is_synthetic = True

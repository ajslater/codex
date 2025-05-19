"""Codex Filesystem Events."""

from abc import ABC
from dataclasses import dataclass

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
)

EVENT_TYPE_START_POLL = "start_poll"
EVENT_TYPE_FINISH_POLL = "finish_poll"


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


@dataclass(unsafe_hash=True)
class CodexPollEvent(FileSystemEvent, ABC):
    """Coex poll event."""

    force: bool = False
    is_synthetic = True


class StartPollEvent(CodexPollEvent):
    """Start Import Task."""

    event_type = EVENT_TYPE_START_POLL


class FinishPollEvent(CodexPollEvent):
    """Finish Import Task."""

    event_type = EVENT_TYPE_FINISH_POLL

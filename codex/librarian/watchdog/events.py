"""
Codex filesystem event dataclasses.

These replace the watchdog event classes with simple dataclasses that carry
just the information codex needs: a path, a change type, and classification
flags for directories and covers.
"""

from dataclasses import dataclass
from enum import IntEnum

from watchfiles import Change


class WatcherChange(IntEnum):
    """Extend watchfiles Change to include moved."""

    added = Change.added
    modified = Change.modified
    deleted = Change.deleted
    moved = deleted + 1


class PollEventType(IntEnum):
    """Poll evenv type."""

    start = 1
    finish = 2


@dataclass(frozen=True, slots=True)
class WatchEvent:
    """A filesystem change event."""

    src_path: str
    change: WatcherChange
    is_directory: bool = False
    is_cover: bool = False
    dest_path: str = ""  # Only populated for moved events

    @property
    def diff_key(self) -> str:
        """Return the ImportTask field name this event maps to."""
        prefix = "covers" if self.is_cover else "dirs" if self.is_directory else "files"
        return f"{prefix}_{self.change.name}"


@dataclass(frozen=True, slots=True)
class PollEvent:
    """Signal the event batcher about poll boundaries."""

    poll_type: PollEventType
    force: bool = False

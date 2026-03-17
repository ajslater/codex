"""Codex filesystem watcher event dataclasses."""

from dataclasses import dataclass
from enum import IntEnum

from watchfiles import Change


class WatcherChange(IntEnum):
    """Extend watchfiles Change to include moved."""

    added = Change.added
    modified = Change.modified
    deleted = Change.deleted
    moved = deleted + 1


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

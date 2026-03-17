"""Poller handlers (snapshot diff: has moved events, dirs, full classification)."""

from dataclasses import dataclass
from enum import IntEnum

from codex.librarian.watcher.events import (
    WatcherChange,
    WatchEvent,
)

_DIFF_FIELD_EVENT_MAP: tuple[tuple[str, WatcherChange, bool, bool], ...] = (
    # diff_attr, change_type, is_directory, is_cover
    ("files_deleted", WatcherChange.deleted, False, False),
    ("files_modified", WatcherChange.modified, False, False),
    ("files_added", WatcherChange.added, False, False),
    ("dirs_deleted", WatcherChange.deleted, True, False),
    ("dirs_modified", WatcherChange.modified, True, False),
)

_DIFF_MOVED_FIELD_EVENT_MAP: tuple[tuple[str, bool, bool], ...] = (
    # diff_attr, is_directory, is_cover
    ("files_moved", False, False),
    ("dirs_moved", True, False),
)


class PollEventType(IntEnum):
    """Poll evenv type."""

    start = 1
    finish = 2


@dataclass(frozen=True, slots=True)
class PollEvent:
    """Signal the event batcher about poll boundaries."""

    poll_type: PollEventType
    force: bool = False


def events_from_diff(diff) -> tuple[WatchEvent, ...]:
    """Convert a SnapshotDiff into a sequence of WatchEvents."""
    events: list[WatchEvent] = []
    events.extend(
        [
            WatchEvent(
                src_path=src_path,
                change=change,
                is_directory=is_dir,
                is_cover=is_cover,
            )
            for attr, change, is_dir, is_cover in _DIFF_FIELD_EVENT_MAP
            for src_path in getattr(diff, attr)
        ]
    )
    events.extend(
        [
            WatchEvent(
                src_path=src_path,
                change=WatcherChange.moved,
                is_directory=is_dir,
                is_cover=is_cover,
                dest_path=dest_path,
            )
            for attr, is_dir, is_cover in _DIFF_MOVED_FIELD_EVENT_MAP
            for src_path, dest_path in getattr(diff, attr)
        ]
    )
    return tuple(events)

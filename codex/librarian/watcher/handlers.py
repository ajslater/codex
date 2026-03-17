"""
Transform raw filesystem changes into watcher events.

These functions classify file changes by matching against comic and cover
file patterns, producing the appropriate WatchEvent instances.
"""

import re
from pathlib import Path

from codex.librarian.watcher.const import COMIC_MATCHER, IMAGE_MATCHER
from codex.librarian.watcher.events import (
    WatcherChange,
    WatchEvent,
)
from codex.models import CustomCover
from codex.settings import CUSTOM_COVERS_DIR, CUSTOM_COVERS_GROUP_DIRS

# Suffix matchers


def _match_suffix(pattern: re.Pattern, path: Path) -> bool:
    return bool(path and path.suffix and pattern.match(path.suffix) is not None)


def _match_folder_cover(path: Path) -> bool:
    """Match a folder cover image (e.g. cover.jpg next to comics)."""
    return path.stem == CustomCover.FOLDER_COVER_STEM and _match_suffix(
        IMAGE_MATCHER, path
    )


def _match_group_cover_image(path_str: str) -> bool:
    """Match a custom group cover image in the custom-covers directory."""
    path = Path(path_str)
    parent = path.parent
    return (
        parent.parent == CUSTOM_COVERS_DIR
        and str(parent.name) in CUSTOM_COVERS_GROUP_DIRS
        and _match_suffix(IMAGE_MATCHER, path)
    )


# Watcher handlers (watchfiles: no moved events, just added/modified/deleted)


def transform_library_change(
    change: WatcherChange, path: str
) -> tuple[WatchEvent, ...]:
    """
    Transform a watchfiles change into codex events for a comic library.

    Handles comic archive files and folder cover images.
    """
    events: list[WatchEvent] = []

    ppath = Path(path)

    if _match_suffix(COMIC_MATCHER, ppath):
        events.append(WatchEvent(src_path=path, change=change))

    if _match_folder_cover(ppath):
        events.append(WatchEvent(src_path=path, change=change, is_cover=True))

    return tuple(events)


def transform_custom_cover_change(
    change: WatcherChange, path: str
) -> tuple[WatchEvent, ...]:
    """Transform a watchfiles change into codex events for the custom cover dir."""
    if _match_group_cover_image(path):
        return (WatchEvent(src_path=path, change=change, is_cover=True),)
    return ()


# Poller handlers (snapshot diff: has moved events, dirs, full classification)

_DIFF_FIELD_EVENT_MAP: tuple[tuple[str, WatcherChange, bool, bool], ...] = (
    # diff_attr, change_type, is_directory, is_cover
    ("files_deleted", WatcherChange.deleted, False, False),
    ("files_modified", WatcherChange.modified, False, False),
    ("files_added", WatcherChange.added, False, False),
    ("dirs_deleted", WatcherChange.deleted, True, False),
    ("dirs_modified", WatcherChange.moved, True, False),
)

_DIFF_MOVED_FIELD_EVENT_MAP: tuple[tuple[str, bool, bool], ...] = (
    # diff_attr, is_directory, is_cover
    ("files_moved", False, False),
    ("dirs_moved", True, False),
)


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

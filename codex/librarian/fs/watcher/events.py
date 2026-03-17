"""
Transform raw filesystem changes into watcher events.

These functions classify file changes by matching against comic and cover
file patterns, producing the appropriate FSEvent instances.
"""

from pathlib import Path

from watchfiles import Change

from codex.librarian.fs.events import (
    FSChange,
    FSEvent,
)
from codex.librarian.fs.filters import (
    match_comic,
    match_folder_cover,
    match_group_cover_image,
)


def _transform_library_change(change: FSChange, path_str: str) -> tuple[FSEvent, ...]:
    """
    Transform a watchfiles change into codex events for a comic library.

    Handles comic archive files and folder cover images.
    """
    events: list[FSEvent] = []

    path = Path(path_str)

    if match_comic(path):
        events.append(FSEvent(src_path=path_str, change=change))

    if match_folder_cover(path):
        events.append(FSEvent(src_path=path_str, change=change, is_cover=True))

    return tuple(events)


def _transform_custom_cover_change(
    change: FSChange, path_str: str
) -> tuple[FSEvent, ...]:
    """Transform a watchfiles change into codex events for the custom cover dir."""
    if match_group_cover_image(Path(path_str)):
        return (FSEvent(src_path=path_str, change=change, is_cover=True),)
    return ()


def watchfile_changes_to_events(
    change_enum: Change,
    path_str: str,
    *,
    covers_only: bool,
):
    """Convert watchfile Changes to Codex FSEvents."""
    change = FSChange(change_enum)
    if covers_only:
        events = _transform_custom_cover_change(change, path_str)
    else:
        events = _transform_library_change(change, path_str)
    return events

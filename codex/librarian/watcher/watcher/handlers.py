"""
Transform raw filesystem changes into watcher events.

These functions classify file changes by matching against comic and cover
file patterns, producing the appropriate WatchEvent instances.
"""

from pathlib import Path

from codex.librarian.watcher.events import (
    WatcherChange,
    WatchEvent,
)
from codex.librarian.watcher.filters import (
    COMIC_MATCHER,
    match_folder_cover,
    match_group_cover_image,
    match_suffix,
)


def transform_library_change(
    change: WatcherChange, path_str: str
) -> tuple[WatchEvent, ...]:
    """
    Transform a watchfiles change into codex events for a comic library.

    Handles comic archive files and folder cover images.
    """
    events: list[WatchEvent] = []

    path = Path(path_str)

    if match_suffix(COMIC_MATCHER, path):
        events.append(WatchEvent(src_path=path_str, change=change))

    if match_folder_cover(path):
        events.append(WatchEvent(src_path=path_str, change=change, is_cover=True))

    return tuple(events)


def transform_custom_cover_change(
    change: WatcherChange, path_str: str
) -> tuple[WatchEvent, ...]:
    """Transform a watchfiles change into codex events for the custom cover dir."""
    if match_group_cover_image(Path(path_str)):
        return (WatchEvent(src_path=path_str, change=change, is_cover=True),)
    return ()

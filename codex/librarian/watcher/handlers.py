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


def match_suffix(pattern: re.Pattern, path: Path) -> bool:
    """Match suffix with pettern."""
    return bool(path and path.suffix and pattern.match(path.suffix) is not None)


def match_folder_cover(path: Path) -> bool:
    """Match a folder cover image (e.g. cover.jpg next to comics)."""
    return path.stem == CustomCover.FOLDER_COVER_STEM and match_suffix(
        IMAGE_MATCHER, path
    )


def match_group_cover_image(path: Path) -> bool:
    """Match a custom group cover image in the custom-covers directory."""
    parent = path.parent
    return (
        parent.parent == CUSTOM_COVERS_DIR
        and str(parent.name) in CUSTOM_COVERS_GROUP_DIRS
        and match_suffix(IMAGE_MATCHER, path)
    )


# Watcher handlers (watchfiles: no moved events, just added/modified/deleted)


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

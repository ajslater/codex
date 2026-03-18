"""
Process raw watchfiles changes into rich FSEvents.

Handles three capabilities that raw watchfiles doesn't provide:
1. Directory added to walk recursively and emit child file events
2. Directory deleted to query DB for orphaned children to delete
3. Move detection to match delete+add pairs by inode within a batch
"""

import os
from collections.abc import Callable
from pathlib import Path

from loguru import logger
from watchfiles import Change

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.fs.filters import (
    match_comic,
    match_folder_cover,
    match_group_cover_image,
)
from codex.models import Comic, CustomCover, FailedImport, Folder

# stat field index for inode
_INODE_INDEX = 1

# Models to query for children when a directory is deleted
_WATCHED_PATH_MODELS = (Folder, Comic, FailedImport, CustomCover)


def _classify_file(path: Path, *, covers_only: bool) -> FSEvent | None:
    """Classify a file path and return an FSEvent if it's relevant, else None."""
    if covers_only:
        if match_group_cover_image(path):
            return FSEvent(src_path=str(path), change=FSChange.added, is_cover=True)
        return None

    if match_comic(path):
        return FSEvent(src_path=str(path), change=FSChange.added)
    if match_folder_cover(path):
        return FSEvent(src_path=str(path), change=FSChange.added, is_cover=True)
    return None


def _expand_dir_added(dir_path: str, *, covers_only: bool) -> list[FSEvent]:
    """Walk a newly added directory and emit events for all matching files."""
    events: list[FSEvent] = []
    root = Path(dir_path)
    if not root.is_dir():
        return events

    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if event := _classify_file(file_path, covers_only=covers_only):
                events.append(event)

    if events:
        logger.debug(f"Expanded dir added {dir_path} to {len(events)} child events")
    return events


def _expand_dir_deleted(dir_path: str, library_pk: int) -> list[FSEvent]:
    """Query the DB for paths under a deleted directory and emit delete events."""
    events: list[FSEvent] = []

    # Delete the folder itself
    events.append(
        FSEvent(src_path=dir_path, change=FSChange.deleted, is_directory=True)
    )

    # Find child folders
    child_folders = Folder.objects.filter(
        library_id=library_pk, path__startswith=dir_path
    ).values_list("path", flat=True)
    events.extend(
        FSEvent(src_path=path, change=FSChange.deleted, is_directory=True)
        for path in child_folders
        if path != dir_path
    )

    # Find child comics and failed imports
    for model in (Comic, FailedImport):
        child_paths = model.objects.filter(
            library_id=library_pk, path__startswith=dir_path
        ).values_list("path", flat=True)
        events.extend(
            FSEvent(src_path=path, change=FSChange.deleted) for path in child_paths
        )

    # Find child custom covers
    child_covers = CustomCover.objects.filter(
        library_id=library_pk, path__startswith=dir_path
    ).values_list("path", flat=True)
    events.extend(
        FSEvent(src_path=path, change=FSChange.deleted, is_cover=True)
        for path in child_covers
    )

    if len(events) > 1:
        logger.debug(f"Expanded dir deleted {dir_path} to {len(events)} child events")
    return events


def _get_db_inode(path: str, library_pk: int) -> int | None:
    """Look up the inode for a path from the database."""
    for model in _WATCHED_PATH_MODELS:
        stat = (
            model.objects.filter(library_id=library_pk, path=path)
            .values_list("stat", flat=True)
            .first()
        )
        if stat and len(stat) > _INODE_INDEX and stat[_INODE_INDEX]:
            return stat[_INODE_INDEX]
    return None


def _get_disk_inode(path: str) -> int | None:
    """Stat a path on disk and return its inode, or None if it doesn't exist."""
    try:
        return Path(path).stat().st_ino
    except OSError:
        return None


def _detect_moves(
    added: list[tuple[str, int, bool]],
    deleted: list[tuple[str, int, bool]],
) -> tuple[list[FSEvent], set[str], set[str]]:
    """
    Match deleted+added pairs by inode to detect moves.

    Args:
        added: list of (path, library_pk, covers_only)
        deleted: list of (path, library_pk, covers_only)

    Returns:
        (move_events, matched_added_paths, matched_deleted_paths)

    """
    move_events: list[FSEvent] = []
    matched_added: set[str] = set()
    matched_deleted: set[str] = set()

    # Build inode → deleted path lookup from the database
    deleted_inode_map: dict[int, tuple[str, int, bool]] = {}
    for del_path, lib_pk, covers_only in deleted:
        inode = _get_db_inode(del_path, lib_pk)
        if inode:
            deleted_inode_map[inode] = (del_path, lib_pk, covers_only)

    if not deleted_inode_map:
        return move_events, matched_added, matched_deleted

    # Check each added path's inode against the deleted set
    for add_path, lib_pk, covers_only in added:
        disk_inode = _get_disk_inode(add_path)
        if not disk_inode:
            continue

        match = deleted_inode_map.get(disk_inode)
        if not match:
            continue

        del_path, del_lib_pk, del_covers_only = match
        # Only match within the same library
        if lib_pk != del_lib_pk:
            continue

        p = Path(add_path)
        is_dir = p.is_dir()
        is_cover = covers_only or del_covers_only

        move_events.append(
            FSEvent(
                src_path=del_path,
                change=FSChange.moved,
                dest_path=add_path,
                is_directory=is_dir,
                is_cover=is_cover,
            )
        )
        matched_added.add(add_path)
        matched_deleted.add(del_path)
        # Remove from map so each inode matches at most once
        del deleted_inode_map[disk_inode]

    if move_events:
        logger.debug(f"Detected {len(move_events)} move(s) from inode matching")

    return move_events, matched_added, matched_deleted


def _process_change_added(
    library_pk: int,
    path: str,
    added_files: list[tuple[str, int, bool]],
    dir_add_events: list[tuple[int, FSEvent]],
    *,
    covers_only: bool,
):
    """If a directory is added. Add events for all it's on disk children."""
    # Feels like watchfiles should do this itself.
    if Path(path).is_dir():
        for event in _expand_dir_added(path, covers_only=covers_only):
            added_files.append((event.src_path, library_pk, covers_only))
            dir_add_events.append((library_pk, event))
    else:
        added_files.append((path, library_pk, covers_only))


def _process_change_deleted(
    library_pk: int,
    path: str,
    dir_delete_events: list[tuple[int, FSEvent]],
    deleted_files: list[tuple[str, int, bool]],
    *,
    covers_only: bool,
):
    """If a delete was a db folder, dive the db and create events for all children."""
    # Feels like watchfiles should do this itself.
    is_known_dir = Folder.objects.filter(library_id=library_pk, path=path).exists()
    if is_known_dir:
        for event in _expand_dir_deleted(path, library_pk):
            if event.is_directory:
                dir_delete_events.append((library_pk, event))
            else:
                deleted_files.append((event.src_path, library_pk, event.is_cover))
    else:
        deleted_files.append((path, library_pk, covers_only))


def _process_change_modified(
    library_pk: int,
    path: str,
    file_events: list[tuple[int, FSEvent]],
    *,
    covers_only: bool,
):
    """Store modified changes unaltered."""
    event = FSEvent(
        src_path=path,
        change=FSChange.modified,
        is_directory=Path(path).is_dir(),
        is_cover=covers_only,
    )
    file_events.append((library_pk, event))


def _add_missing_child_events(
    library_lookup: Callable[[str], tuple[int, bool] | None],
    path: str,
    change_enum: Change,
    added_files: list[tuple[str, int, bool]],
    dir_add_events: list[tuple[int, FSEvent]],
    dir_delete_events: list[tuple[int, FSEvent]],
    deleted_files: list[tuple[str, int, bool]],
    file_events: list[tuple[int, FSEvent]],
):
    result = library_lookup(path)
    if not result:
        return
    library_pk, covers_only = result

    if change_enum == Change.added:
        _process_change_added(
            library_pk,
            path,
            added_files,
            dir_add_events,
            covers_only=covers_only,
        )
    elif change_enum == Change.deleted:
        _process_change_deleted(
            library_pk,
            path,
            dir_delete_events,
            deleted_files,
            covers_only=covers_only,
        )
    elif change_enum == Change.modified:
        _process_change_modified(library_pk, path, file_events, covers_only=covers_only)


def _consolidate_move_events(
    added_files, deleted_files, dir_add_events, library_lookup
):
    # Detect moves from matching inodes between deleted and added
    move_events, matched_added, matched_deleted = _detect_moves(
        added_files, deleted_files
    )

    # Build final output
    output: list[tuple[int, FSEvent]] = []

    # Add move events
    for event in move_events:
        # Find the library for the move (use the dest path's library)
        result = library_lookup(event.dest_path)
        if result:
            output.append((result[0], event))

    # Add unmatched added events
    output.extend(
        (
            lib_pk,
            FSEvent(src_path=path, change=FSChange.added, is_cover=covers_only),
        )
        for path, lib_pk, covers_only in added_files
        if path not in matched_added
    )

    # Add unmatched deleted events
    output.extend(
        (
            lib_pk,
            FSEvent(src_path=path, change=FSChange.deleted, is_cover=covers_only),
        )
        for path, lib_pk, covers_only in deleted_files
        if path not in matched_deleted
    )

    # Add dir-added child events that weren't matched as moves
    for lib_pk, event in dir_add_events:
        if event.src_path not in matched_added:
            output.append((lib_pk, event))

    return output


def process_changes(
    changes: set[tuple[Change, str]],
    library_lookup: Callable[[str], tuple[int, bool] | None],
) -> list[tuple[int, FSEvent]]:
    """
    Process a batch of raw watchfiles changes into (library_pk, FSEvent) pairs.

    Args:
        changes: raw watchfiles change set
        library_lookup: callable(path) returning (library_pk, covers_only) or None

    """
    # Separate changes by type, filtering to relevant files.
    # Track dir adds/deletes for expansion; file adds/deletes for move detection.
    added_files: list[tuple[str, int, bool]] = []  # path, lib_pk, covers_only
    deleted_files: list[tuple[str, int, bool]] = []
    file_events: list[tuple[int, FSEvent]] = []  # non-add/delete events (modified)
    dir_add_events: list[tuple[int, FSEvent]] = []
    dir_delete_events: list[tuple[int, FSEvent]] = []

    # Add missing events for added and deleted folders
    for change_enum, path in changes:
        _add_missing_child_events(
            library_lookup,
            path,
            change_enum,
            added_files,
            dir_add_events,
            dir_delete_events,
            deleted_files,
            file_events,
        )

    output = _consolidate_move_events(
        added_files, deleted_files, dir_add_events, library_lookup
    )

    # Add dir delete events (these are always emitted — not subject to move matching)
    output.extend(dir_delete_events)

    # Add modified events
    output.extend(file_events)

    return output

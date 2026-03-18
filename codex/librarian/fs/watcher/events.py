"""
Process raw watchfiles changes into rich FSEvents.

Handles three capabilities that raw watchfiles doesn't provide:
1. Directory added -> walk recursively and emit child file events
2. Directory deleted -> query DB for orphaned children to delete
3. Move detection -> match delete+add pairs by inode within a batch
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field
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


@dataclass
class _ChangeBatch:
    """Accumulated changes from a single watchfiles batch."""

    # (library_pk, FSEvent) pairs, grouped by change type
    added: list[tuple[int, FSEvent]] = field(default_factory=list)
    deleted: list[tuple[int, FSEvent]] = field(default_factory=list)
    modified: list[tuple[int, FSEvent]] = field(default_factory=list)
    # Dir deletes expanded from DB, kept separate so they bypass move matching
    dir_deleted: list[tuple[int, FSEvent]] = field(default_factory=list)


######################################
# Add missing events for directories #
######################################


def _classify_added_file(path: Path, *, covers_only: bool) -> FSEvent | None:
    """Return an added FSEvent if the path is a relevant file, else None."""
    if covers_only:
        if match_group_cover_image(path):
            return FSEvent(src_path=str(path), change=FSChange.added, is_cover=True)
        return None
    if match_comic(path):
        return FSEvent(src_path=str(path), change=FSChange.added)
    if match_folder_cover(path):
        return FSEvent(src_path=str(path), change=FSChange.added, is_cover=True)
    return None


def _expand_dir_added(
    dir_path: str,
    library_pk: int,
    batch: _ChangeBatch,
    *,
    covers_only: bool,
) -> None:
    """Walk a newly added directory and add child events to the batch."""
    root = Path(dir_path)
    if not root.is_dir():
        return
    count = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if event := _classify_added_file(file_path, covers_only=covers_only):
                batch.added.append((library_pk, event))
                count += 1
    if count:
        logger.debug(f"Expanded dir added {dir_path} -> {count} child events")


def _expand_dir_deleted(dir_path: str, library_pk: int, batch: _ChangeBatch) -> None:
    """Query the DB for paths under a deleted directory and add events to the batch."""
    # The directory itself
    batch.dir_deleted.append(
        (
            library_pk,
            FSEvent(src_path=dir_path, change=FSChange.deleted, is_directory=True),
        )
    )

    # Child folders
    child_folder_paths = Folder.objects.filter(
        library_id=library_pk, path__startswith=dir_path
    ).values_list("path", flat=True)
    for path in child_folder_paths:
        if path != dir_path:
            batch.dir_deleted.append(
                (
                    library_pk,
                    FSEvent(src_path=path, change=FSChange.deleted, is_directory=True),
                )
            )

    # Child comics and failed imports
    for model in (Comic, FailedImport):
        child_paths = model.objects.filter(
            library_id=library_pk, path__startswith=dir_path
        ).values_list("path", flat=True)
        for path in child_paths:
            batch.deleted.append(
                (library_pk, FSEvent(src_path=path, change=FSChange.deleted))
            )

    # Child custom covers
    cover_paths = CustomCover.objects.filter(
        library_id=library_pk, path__startswith=dir_path
    ).values_list("path", flat=True)
    for path in cover_paths:
        batch.deleted.append(
            (
                library_pk,
                FSEvent(src_path=path, change=FSChange.deleted, is_cover=True),
            )
        )


##################
# Move detection #
##################


def _model_for_event(event: FSEvent):
    """Return the single Django model to query for this event's inode."""
    if event.is_cover:
        return CustomCover
    if event.is_directory:
        return Folder
    return Comic


def _get_db_inode(event: FSEvent, library_pk: int) -> int | None:
    """Look up the inode for a path from the database stat field."""
    model = _model_for_event(event)
    stat = (
        model.objects.filter(library_id=library_pk, path=event.src_path)
        .values_list("stat", flat=True)
        .first()
    )
    if stat and len(stat) > _INODE_INDEX and stat[_INODE_INDEX]:
        return stat[_INODE_INDEX]
    return None


def _get_disk_inode(path: str) -> int | None:
    """Stat a path on disk and return its inode, or None."""
    try:
        return os.stat(path).st_ino  # noqa: PTH116
    except OSError:
        return None


def _detect_moves(batch: _ChangeBatch) -> list[tuple[int, FSEvent]]:
    """
    Match deleted+added pairs by inode to detect moves.

    Returns move events. Matched FSEvents are removed from batch.added
    and batch.deleted in place.
    """
    # Build inode -> (index, library_pk, event) from deleted list
    deleted_by_inode: dict[int, tuple[int, int, FSEvent]] = {}
    for idx, (lib_pk, event) in enumerate(batch.deleted):
        inode = _get_db_inode(event, lib_pk)
        if inode:
            deleted_by_inode[inode] = (idx, lib_pk, event)

    if not deleted_by_inode:
        return []

    move_events: list[tuple[int, FSEvent]] = []
    matched_added: set[int] = set()  # indices into batch.added
    matched_deleted: set[int] = set()  # indices into batch.deleted

    for add_idx, (add_lib_pk, add_event) in enumerate(batch.added):
        disk_inode = _get_disk_inode(add_event.src_path)
        if not disk_inode:
            continue

        match = deleted_by_inode.get(disk_inode)
        if not match:
            continue

        del_idx, del_lib_pk, del_event = match
        # Only match within the same library
        if add_lib_pk != del_lib_pk:
            continue

        is_dir = Path(add_event.src_path).is_dir()
        is_cover = add_event.is_cover or del_event.is_cover

        move_events.append(
            (
                add_lib_pk,
                FSEvent(
                    src_path=del_event.src_path,
                    change=FSChange.moved,
                    dest_path=add_event.src_path,
                    is_directory=is_dir,
                    is_cover=is_cover,
                ),
            )
        )
        matched_added.add(add_idx)
        matched_deleted.add(del_idx)
        del deleted_by_inode[disk_inode]

    # Remove matched entries from added and deleted (reverse order to keep indices valid)
    batch.added = [
        pair for idx, pair in enumerate(batch.added) if idx not in matched_added
    ]
    batch.deleted = [
        pair for idx, pair in enumerate(batch.deleted) if idx not in matched_deleted
    ]

    if move_events:
        logger.debug(f"Detected {len(move_events)} move(s) from inode matching")

    return move_events


#######################
# Process each change #
#######################


def _process_change(
    change_enum: Change,
    path: str,
    library_pk: int,
    batch: _ChangeBatch,
    *,
    covers_only: bool,
) -> None:
    """Classify a single raw change and append to the batch."""
    p = Path(path)

    if change_enum == Change.added:
        if p.is_dir():
            _expand_dir_added(path, library_pk, batch, covers_only=covers_only)
        else:
            batch.added.append(
                (
                    library_pk,
                    FSEvent(src_path=path, change=FSChange.added, is_cover=covers_only),
                )
            )

    elif change_enum == Change.deleted:
        is_known_dir = Folder.objects.filter(library_id=library_pk, path=path).exists()
        if is_known_dir:
            _expand_dir_deleted(path, library_pk, batch)
        else:
            batch.deleted.append(
                (
                    library_pk,
                    FSEvent(
                        src_path=path, change=FSChange.deleted, is_cover=covers_only
                    ),
                )
            )

    elif change_enum == Change.modified:
        is_dir = p.is_dir()
        batch.modified.append(
            (
                library_pk,
                FSEvent(
                    src_path=path,
                    change=FSChange.modified,
                    is_directory=is_dir,
                    is_cover=covers_only,
                ),
            )
        )


def process_changes(
    changes: set[tuple[Change, str]],
    library_lookup: Callable[[str], tuple[int, bool] | None],
) -> list[tuple[int, FSEvent]]:
    """
    Process a batch of raw watchfiles changes into (library_pk, FSEvent) pairs.

    library_lookup is called exactly once per raw change. All downstream
    processing uses the library_pk stored in the batch.
    """
    batch = _ChangeBatch()

    # Single pass: classify each raw change, calling library_lookup once each
    for change_enum, path in changes:
        result = library_lookup(path)
        if not result:
            continue
        library_pk, covers_only = result
        _process_change(change_enum, path, library_pk, batch, covers_only=covers_only)

    # Detect moves (mutates batch.added and batch.deleted in place)
    move_events = _detect_moves(batch)

    # Assemble output: moves + remaining adds + remaining deletes + dir deletes + modified
    output: list[tuple[int, FSEvent]] = []
    output.extend(move_events)
    output.extend(batch.added)
    output.extend(batch.deleted)
    output.extend(batch.dir_deleted)
    output.extend(batch.modified)
    return output

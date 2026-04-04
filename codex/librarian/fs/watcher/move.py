"""Watchfiles Move detection."""

from pathlib import Path

from loguru import logger

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.fs.watcher.data import ChangeBatch
from codex.models.comic import Comic
from codex.models.groups import Folder
from codex.models.paths import CustomCover

# stat field index for inode
_INODE_INDEX = 1


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
        p = Path(path)
        return p.stat().st_ino
    except OSError:
        return None


def _detect_one_move(
    add_idx: int,
    add_value: tuple[int, FSEvent],
    deleted_by_inode,
    move_events,
    matched_added,
    matched_deleted,
) -> None:
    add_lib_pk, add_event = add_value
    disk_inode = _get_disk_inode(add_event.src_path)
    if not disk_inode:
        return

    match = deleted_by_inode.get(disk_inode)
    if not match:
        return

    del_idx, del_lib_pk, del_event = match
    # Only match within the same library
    if add_lib_pk != del_lib_pk:
        return

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


def detect_moves(batch: ChangeBatch) -> list[tuple[int, FSEvent]]:
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

    for add_idx, add_val in enumerate(batch.added):
        _detect_one_move(
            add_idx,
            add_val,
            deleted_by_inode,
            move_events,
            matched_added,
            matched_deleted,
        )
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

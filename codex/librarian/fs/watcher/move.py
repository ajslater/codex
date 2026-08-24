"""Watchfiles Move detection."""

import os
from dataclasses import dataclass
from pathlib import Path
from stat import S_IFMT, S_ISDIR

from loguru import logger

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.fs.watcher.data import ChangeBatch
from codex.models.collections import Folder
from codex.models.comic import Comic
from codex.models.paths import CustomCover

# stat field indexes, as stored by WatchedPath.set_stat
_MODE_INDEX = 0
_INODE_INDEX = 1
_SIZE_INDEX = 6


@dataclass(frozen=True, slots=True)
class _DeletedEntry:
    """A deleted path that could be the source of a move."""

    index: int
    library_pk: int
    event: FSEvent
    stat: list
    # The same batch also reports this path as written, so its stored
    # size predates that write. See ``_is_move_compatible``.
    written: bool


def _model_for_event(event: FSEvent):
    """Return the single Django model to query for this event's inode."""
    if event.is_cover:
        return CustomCover
    if event.is_directory:
        return Folder
    return Comic


def _get_db_stat(event: FSEvent, library_pk: int) -> list | None:
    """Return the stored stat for a path, when it carries a usable inode."""
    model = _model_for_event(event)
    stat = (
        model.objects.filter(library_id=library_pk, path=event.src_path)
        .values_list("stat", flat=True)
        .first()
    )
    if stat and len(stat) > _INODE_INDEX and stat[_INODE_INDEX]:
        return stat
    return None


def _get_disk_stat(path: str) -> os.stat_result | None:
    """Stat a path on disk, or None when it can't be read."""
    try:
        return Path(path).stat()
    except OSError:
        return None


def _is_move_compatible(entry: _DeletedEntry, disk_stat: os.stat_result) -> bool:
    """
    Reject inode-match pairs that can't be a real rename.

    Ported from the poller's identically-named check (see
    ``codex.librarian.fs.poller.snapshot_diff``), which the watcher needs
    for the same reason and for one of its own. Stored inodes carry no
    device, so a deleted path's inode can collide with an added path from
    another mount; and a bulk CBR->CBZ conversion frees many inodes while
    creating many files, so on an inode-reusing filesystem a new CBZ can
    be handed the inode a *different* comic's CBR just released. Pairing
    either re-paths one comic's row onto another comic's file.

    Two cheap sanity checks make the inode match load-bearing only when
    it's plausibly a rename:

    - File type must match. A real rename never crosses ``stat()``
      file-type bits, so a mode mismatch is always a collision.
    - For files, size must match too. Renames preserve size, and two
      unrelated archives are vanishingly unlikely to share a byte count.
      Directory ``st_size`` varies with entry count, so it is exempt.

    The size check compares against the size stored at import, so it only
    holds while that is still current. A tagger that writes tags in place
    and then renames — the flow ``build_import_task`` remaps modify
    events for — changes the size before the rename, so a batch that also
    reports the source as written waives the size check rather than
    dropping a real pair.
    """
    db_stat = entry.stat
    db_mode = db_stat[_MODE_INDEX] if len(db_stat) > _MODE_INDEX else 0
    if db_mode and S_IFMT(db_mode) != S_IFMT(disk_stat.st_mode):
        return False
    if entry.written or S_ISDIR(disk_stat.st_mode):
        return True
    db_size = db_stat[_SIZE_INDEX] if len(db_stat) > _SIZE_INDEX else None
    return db_size is None or db_size == disk_stat.st_size


def _detect_one_move(
    add_idx: int,
    add_value: tuple[int, FSEvent],
    deleted_by_inode,
    move_events,
    matched_added,
    matched_deleted,
) -> None:
    add_lib_pk, add_event = add_value
    disk_stat = _get_disk_stat(add_event.src_path)
    if not disk_stat or not disk_stat.st_ino:
        return

    entry = deleted_by_inode.get(disk_stat.st_ino)
    if not entry:
        return

    # Only match within the same library
    if add_lib_pk != entry.library_pk:
        return

    if not _is_move_compatible(entry, disk_stat):
        return

    is_dir = S_ISDIR(disk_stat.st_mode)
    is_cover = add_event.is_cover or entry.event.is_cover

    move_events.append(
        (
            add_lib_pk,
            FSEvent(
                src_path=entry.event.src_path,
                change=FSChange.moved,
                dest_path=add_event.src_path,
                is_directory=is_dir,
                is_cover=is_cover,
            ),
        )
    )
    matched_added.add(add_idx)
    matched_deleted.add(entry.index)
    del deleted_by_inode[disk_stat.st_ino]


def _index_deleted(batch: ChangeBatch) -> dict[int, _DeletedEntry]:
    """Build inode -> deleted entry from the batch's deleted list."""
    written_paths = frozenset(event.src_path for _, event in batch.modified)
    deleted_by_inode: dict[int, _DeletedEntry] = {}
    for idx, (lib_pk, event) in enumerate(batch.deleted):
        stat = _get_db_stat(event, lib_pk)
        if not stat:
            continue
        deleted_by_inode[stat[_INODE_INDEX]] = _DeletedEntry(
            index=idx,
            library_pk=lib_pk,
            event=event,
            stat=stat,
            written=event.src_path in written_paths,
        )
    return deleted_by_inode


def detect_moves(batch: ChangeBatch) -> list[tuple[int, FSEvent]]:
    """
    Match deleted+added pairs by inode to detect moves.

    Returns move events. Matched FSEvents are removed from batch.added
    and batch.deleted in place.
    """
    deleted_by_inode = _index_deleted(batch)
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
    # Drop the matched entries; the move events carry them now.
    batch.added = [
        pair for idx, pair in enumerate(batch.added) if idx not in matched_added
    ]
    batch.deleted = [
        pair for idx, pair in enumerate(batch.deleted) if idx not in matched_deleted
    ]

    if move_events:
        logger.debug(f"Detected {len(move_events)} move(s) from inode matching")

    return move_events

"""
Process raw watchfiles changes into rich FSEvents.

Handles three capabilities that raw watchfiles doesn't provide:
1. Directory added -> walk recursively and emit child file events
2. Directory deleted -> query DB for orphaned children to delete
3. Move detection -> match delete+add pairs by inode within a batch
"""

from pathlib import Path

from watchfiles import Change

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.fs.watcher.data import ChangeBatch
from codex.librarian.fs.watcher.dirs import expand_dir_added, expand_dir_deleted
from codex.librarian.fs.watcher.move import detect_moves
from codex.models.groups import Folder


def _process_change(
    change_enum: Change,
    path: str,
    library_pk: int,
    batch: ChangeBatch,
) -> None:
    """Classify a single raw change and append to the batch."""
    p = Path(path)

    if change_enum == Change.added:
        if p.is_dir():
            expand_dir_added(path, library_pk, batch)
        else:
            batch.added.append(
                (
                    library_pk,
                    FSEvent(src_path=path, change=FSChange.added),
                )
            )

    elif change_enum == Change.deleted:
        is_known_dir = Folder.objects.filter(library_id=library_pk, path=path).exists()
        if is_known_dir:
            expand_dir_deleted(path, library_pk, batch)
        else:
            batch.deleted.append(
                (
                    library_pk,
                    FSEvent(src_path=path, change=FSChange.deleted),
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
                ),
            )
        )


def _find_library(library_paths: dict[str, int], file_path: str) -> int | None:
    """Find which library a changed path belongs to."""
    for lib_path, pk in library_paths.items():
        if file_path.startswith(lib_path):
            return pk
    return None


def process_changes(
    changes: set[tuple[Change, str]],
    library_paths: dict[str, int],
) -> list[tuple[int, FSEvent]]:
    """
    Process a batch of raw watchfiles changes into (library_pk, FSEvent) pairs.

    library_lookup is called exactly once per raw change. All downstream
    processing uses the library_pk stored in the batch.
    """
    batch = ChangeBatch()

    # Single pass: classify each raw change, calling library_lookup once each
    for change_enum, path in changes:
        library_pk = _find_library(library_paths, path)
        if library_pk is None:
            continue
        _process_change(change_enum, path, library_pk, batch)

    # Detect moves (mutates batch.added and batch.deleted in place)
    move_events = detect_moves(batch)

    # Assemble output: moves + remaining adds + remaining deletes + dir deletes + modified
    output: list[tuple[int, FSEvent]] = []
    output.extend(move_events)
    output.extend(batch.added)
    output.extend(batch.deleted)
    output.extend(batch.dir_deleted)
    output.extend(batch.modified)
    return output

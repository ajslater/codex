"""Add missing events for directories."""

import os
from pathlib import Path

from loguru import logger

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.fs.filters import is_ignored_basename, match_comic
from codex.librarian.fs.watcher.data import ChangeBatch
from codex.models.comic import Comic
from codex.models.groups import Folder
from codex.models.paths import FailedImport


def _classify_added_file(path: Path) -> FSEvent | None:
    """Return an added FSEvent if the path is a relevant file, else None."""
    if match_comic(path):
        return FSEvent(src_path=str(path), change=FSChange.added)
    return None


def expand_dir_added(
    dir_path: str,
    library_pk: int,
    batch: ChangeBatch,
) -> None:
    """Walk a newly added directory and add child events to the batch."""
    root = Path(dir_path)
    if not root.is_dir():
        return
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in place so ``os.walk`` never
        # descends into them under a freshly-added tree. Rules come
        # from the central registry in ``filters`` — extend that
        # module to add more patterns.
        dirnames[:] = [d for d in dirnames if not is_ignored_basename(d)]
        for filename in filenames:
            if is_ignored_basename(filename):
                continue
            file_path = Path(dirpath) / filename
            if event := _classify_added_file(file_path):
                batch.added.append((library_pk, event))
                count += 1
    if count:
        logger.debug(f"Expanded dir added {dir_path} -> {count} child events")


def expand_dir_deleted(dir_path: str, library_pk: int, batch: ChangeBatch) -> None:
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

"""Build deduplicated ImportTasks from filesystem events."""

from collections.abc import Iterable
from contextlib import suppress
from copy import deepcopy
from types import MappingProxyType
from typing import Any

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.scribe.importer.tasks import ImportTask

_IMPORT_TASK_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
    {
        "dirs_moved": {},
        "dirs_modified": set(),
        "dirs_deleted": set(),
        "files_moved": {},
        "files_modified": set(),
        "files_added": set(),
        "files_deleted": set(),
        "covers_moved": {},
        "covers_modified": set(),
        "covers_added": set(),
        "covers_deleted": set(),
    }
)


def _create_kwargs(library_id: int) -> dict[str, Any]:
    kwargs = deepcopy(dict(_IMPORT_TASK_KWARGS))
    kwargs["library_id"] = library_id
    return kwargs


def _add_event(kwargs: dict[str, Any], event: FSEvent) -> None:
    field = kwargs.get(event.diff_key)
    if field is None:
        return
    if event.change == FSChange.moved:
        field[event.src_path] = event.dest_path
    else:
        field.add(event.src_path)


def _remove_paths(kwargs: dict[str, Any], deleted_key: str, moved_key: str) -> None:
    for src_path in kwargs[deleted_key]:
        with suppress(KeyError):
            del kwargs[moved_key][src_path]


def _replaced_paths(kwargs: dict[str, Any], added_key: str, deleted_key: str) -> set:
    """
    Take paths reported both deleted and added; they were replaced in place.

    An external tool that swaps a file by ``rm`` + ``mv``, or a watcher
    backend that reports an atomic replace as a delete plus an add, leaves
    both events in one batch. The recreated file carries a new inode, so
    move detection can never pair them — and letting the delete win would
    destroy the row, and its bookmarks, while a file sits at that very
    path. It is the same path with new content: a modification.
    """
    replaced = kwargs[added_key] & kwargs[deleted_key]
    kwargs[added_key] -= replaced
    kwargs[deleted_key] -= replaced
    return replaced


def _deduplicate(kwargs: dict[str, Any]) -> None:
    """Prune conflicting events on the same paths."""
    replaced_files = _replaced_paths(kwargs, "files_added", "files_deleted")
    replaced_covers = _replaced_paths(kwargs, "covers_added", "covers_deleted")

    # deleted wins over moved-from-this-source
    _remove_paths(kwargs, "dirs_deleted", "dirs_moved")
    _remove_paths(kwargs, "files_deleted", "files_moved")

    # added: drop if also deleted, or if it's the dest of a move
    kwargs["files_added"] -= kwargs["files_deleted"]
    files_dest_paths = set(kwargs["files_moved"].values())
    kwargs["files_added"] -= files_dest_paths

    # modified: redundant if the path is also deleted, added, or move-dest
    kwargs["dirs_modified"] -= kwargs["dirs_deleted"]
    kwargs["dirs_modified"] -= set(kwargs["dirs_moved"].values())

    kwargs["files_modified"] -= kwargs["files_added"]
    kwargs["files_modified"] -= kwargs["files_deleted"]
    # A modified path that takes part in a move refers to content that now
    # lives at the destination. The watcher emits the source path (an
    # external tagger writing tags and then renaming produces the modify
    # before the rename), while the poller emits the destination path on
    # purpose for a move whose stats also changed. Remap sources and keep
    # destinations so both reach the read phase alive. A pure rename's
    # destination costs only a stat() there, because a move preserves the
    # stored stat (see MOVED_BULK_COMIC_UPDATE_FIELDS).
    files_moved = kwargs["files_moved"]
    kwargs["files_modified"] = {
        files_moved.get(path, path) for path in kwargs["files_modified"]
    }

    kwargs["covers_modified"] -= kwargs["covers_deleted"]
    kwargs["covers_modified"] -= kwargs["covers_added"]

    # Added last: a replaced path is neither created nor deleted, and the
    # subtractions above would have stripped it back out.
    kwargs["files_modified"] |= replaced_files
    kwargs["covers_modified"] |= replaced_covers


def build_import_task(
    library_id: int,
    events: Iterable[FSEvent],
    *,
    check_metadata_mtime: bool = True,
) -> ImportTask | None:
    """
    Build a deduplicated ImportTask from a batch of FSEvents.

    Returns ``None`` if the batch contains no work after dedup.
    """
    kwargs = _create_kwargs(library_id)
    for event in events:
        _add_event(kwargs, event)
    _deduplicate(kwargs)
    kwargs["files_created"] = kwargs.pop("files_added")
    kwargs["covers_created"] = kwargs.pop("covers_added")
    kwargs["check_metadata_mtime"] = check_metadata_mtime
    task = ImportTask(**kwargs)
    if not task.total():
        return None
    return task

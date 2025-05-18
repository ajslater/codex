"""Mixin to aggregate Watchdog Events."""

from contextlib import suppress
from copy import deepcopy
from types import MappingProxyType

from watchdog.events import (
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
)

from codex.librarian.watchdog.events import (
    CoverCreatedEvent,
    CoverDeletedEvent,
    CoverModifiedEvent,
    CoverMovedEvent,
)

EVENT_CLASS_DIFF_ATTR_MAP = MappingProxyType(
    {
        FileDeletedEvent: "files_deleted",
        FileModifiedEvent: "files_modified",
        FileCreatedEvent: "files_created",
        DirDeletedEvent: "dirs_deleted",
        DirModifiedEvent: "dirs_modified",
    }
)
EVENT_MOVED_CLASS_DIFF_ATTR_MAP = MappingProxyType(
    {FileMovedEvent: "files_moved", DirMovedEvent: "dirs_moved"}
)
EVENT_COVERS_DIFF_ATTR_MAP = MappingProxyType(
    {
        CoverCreatedEvent: "covers_created",
        CoverDeletedEvent: "covers_deleted",
        CoverModifiedEvent: "covers_modified",
    }
)
EVENT_COVERS_MOVED_CLASS_DIFF_ATTR_MAP = MappingProxyType(
    {CoverMovedEvent: "covers_moved"}
)

EVENT_CLASS_DIFF_ALL_MAP: MappingProxyType[type[FileSystemEvent], str] = (
    MappingProxyType(
        {
            **EVENT_CLASS_DIFF_ATTR_MAP,
            **EVENT_MOVED_CLASS_DIFF_ATTR_MAP,
            **EVENT_COVERS_DIFF_ATTR_MAP,
            **EVENT_COVERS_MOVED_CLASS_DIFF_ATTR_MAP,
        }
    )
)
_IMPORT_TASK_PARAMS = MappingProxyType(
    {
        "dirs_moved": {},
        "dirs_modified": set(),
        "dirs_deleted": set(),
        "files_moved": {},
        "files_modified": set(),
        "files_created": set(),
        "files_deleted": set(),
        "covers_moved": {},
        "covers_modified": set(),
        "covers_created": set(),
        "covers_deleted": set(),
    }
)


class EventAggregatorMixin:
    """Mixin to aggregate Watchdog Events."""

    @classmethod
    def create_import_task_args(cls, library_id: int) -> dict:
        """Create import task args."""
        args = deepcopy(dict(_IMPORT_TASK_PARAMS))
        args["library_id"] = library_id  # pyright: ignore[reportArgumentType]
        return args

    @staticmethod
    def key_for_event(event: FileSystemEvent) -> str:
        """Return the args field name for the event."""
        return EVENT_CLASS_DIFF_ALL_MAP[type(event)]

    @staticmethod
    def _remove_paths(args, deleted_key: str, moved_key: str):
        for src_path in args[deleted_key]:
            with suppress(KeyError):
                del args[moved_key][src_path]

    @classmethod
    def deduplicate_events(cls, args: dict):
        """Prune different event types on the same paths."""
        # deleted
        cls._remove_paths(args, "dirs_deleted", "dirs_moved")
        cls._remove_paths(args, "files_deleted", "files_moved")

        # created
        args["files_created"] -= args["files_deleted"]
        files_dest_paths = set(args["files_moved"].values())
        args["files_created"] -= files_dest_paths

        # modified
        args["dirs_modified"] -= args["dirs_deleted"]
        args["dirs_modified"] -= set(args["dirs_moved"].values())

        args["files_modified"] -= args["files_created"]
        args["files_modified"] -= args["files_deleted"]
        args["files_modified"] -= files_dest_paths

        args["covers_modified"] -= args["covers_deleted"]
        args["covers_modified"] -= args["covers_created"]

"""Mixin to aggregate Watchdog Events."""

from contextlib import suppress
from copy import deepcopy
from types import MappingProxyType

from watchdog.events import FileSystemEvent


class EventAggregatorMixin:
    """Mixin to aggregate Watchdog Events."""

    IMPORT_TASK_PARAMS = MappingProxyType(
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

    @classmethod
    def create_import_task_args(cls, library_id: int) -> dict:
        """Create import task args."""
        args = deepcopy(dict(cls.IMPORT_TASK_PARAMS))
        args["library_id"] = library_id  # pyright: ignore[reportArgumentType]
        return args

    @staticmethod
    def key_for_event(event: FileSystemEvent) -> str:
        """Return the args field name for the event."""
        prefix = (
            "dir"
            if event.is_directory
            else "cover"
            if getattr(event, "is_cover", False)
            else "file"
        )
        return f"{prefix}s_{event.event_type}"

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

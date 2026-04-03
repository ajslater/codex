"""
Compute the diff between two snapshots.

Supports inode-based move detection and optional device-ignoring for
Docker/complex filesystems.
"""

from dataclasses import dataclass

from codex.librarian.fs.events import (
    FSChange,
    FSEvent,
)
from codex.librarian.fs.poller.snapshot import Snapshot

_DIFF_FIELD_EVENT_MAP: tuple[tuple[str, FSChange, bool, bool], ...] = (
    # diff_attr, change_type, is_directory, is_cover
    ("files_deleted", FSChange.deleted, False, False),
    ("files_modified", FSChange.modified, False, False),
    ("files_added", FSChange.added, False, False),
    ("dirs_deleted", FSChange.deleted, True, False),
    ("dirs_modified", FSChange.modified, True, False),
)

_DIFF_MOVED_FIELD_EVENT_MAP: tuple[tuple[str, bool, bool], ...] = (
    # diff_attr, is_directory, is_cover
    ("files_moved", False, False),
    ("dirs_moved", True, False),
)


@dataclass
class _DiffData:
    """Mutable working state for diff computation."""

    ref: Snapshot
    snapshot: Snapshot
    added: set[str]
    deleted: set[str]
    modified: set[str]
    moved: set[tuple[str, str]]
    unchanged: frozenset[str]


class SnapshotDiff:
    """Diff between a reference snapshot and a new snapshot."""

    def __init__(
        self,
        ref: Snapshot,
        snapshot: Snapshot,
    ) -> None:
        """Compute the diff between ref (old/database) and snapshot (new/disk)."""
        data = _DiffData(
            ref=ref,
            snapshot=snapshot,
            added=set(snapshot.paths - ref.paths),
            deleted=set(ref.paths - snapshot.paths),
            modified=set(),
            moved=set(),
            unchanged=frozenset(ref.paths & snapshot.paths),
        )

        self._check_unchanged_for_inode_changes(data)
        self._find_moved_paths(data)
        self._find_modified_paths(data)

        self.dirs_added = [p for p in data.added if snapshot.is_dir(p)]
        self.dirs_deleted = [p for p in data.deleted if ref.is_dir(p)]
        self.dirs_modified = [p for p in data.modified if snapshot.is_dir(p)]
        self.dirs_moved = [(f, t) for f, t in data.moved if ref.is_dir(f)]

        dir_added_set = set(self.dirs_added)
        dir_deleted_set = set(self.dirs_deleted)
        dir_modified_set = set(self.dirs_modified)
        dir_moved_set = set(self.dirs_moved)

        self.files_added = list(data.added - dir_added_set)
        self.files_deleted = list(data.deleted - dir_deleted_set)
        self.files_modified = list(data.modified - dir_modified_set)
        self.files_moved = list(data.moved - dir_moved_set)

    def _is_inode_equal(self, data: _DiffData, path: str) -> bool:
        """Return whether inodes match between ref and snapshot."""
        return data.ref.inode(path) == data.snapshot.inode(path)

    def _is_stats_equal(self, data: _DiffData, old_path: str, new_path: str) -> bool:
        """Return whether mtime and size match."""
        return data.ref.mtime(old_path) == data.snapshot.mtime(
            new_path
        ) and data.ref.size(old_path) == data.snapshot.size(new_path)

    def _check_unchanged_for_inode_changes(self, data: _DiffData) -> None:
        """Check unchanged paths for inode changes (file replaced in-place)."""
        for path in data.unchanged:
            if not self._is_inode_equal(data, path):
                data.modified.add(path)

    def _find_moved_paths(self, data: _DiffData) -> None:
        """Detect moves by matching inodes between deleted and added sets."""
        for old_path in tuple(data.deleted):
            inode = data.ref.inode(old_path)
            if new_path := data.snapshot.path(inode):
                data.deleted.remove(old_path)
                data.moved.add((old_path, new_path))

        for new_path in tuple(data.added):
            inode = data.snapshot.inode(new_path)
            if old_path := data.ref.path(inode):
                data.added.remove(new_path)
                data.moved.add((old_path, new_path))

    def _find_modified_paths(self, data: _DiffData) -> None:
        """Find paths with changed stats (mtime/size)."""
        for path in data.unchanged:
            if self._is_inode_equal(data, path) and not self._is_stats_equal(
                data, path, path
            ):
                data.modified.add(path)

        for old_path, new_path in data.moved:
            if not self._is_stats_equal(data, old_path, new_path):
                data.modified.add(new_path)

    def is_empty(self) -> bool:
        """Return True if no changes were detected."""
        return not any(
            (
                self.files_added,
                self.files_deleted,
                self.files_modified,
                self.files_moved,
                self.dirs_added,
                self.dirs_deleted,
                self.dirs_modified,
                self.dirs_moved,
            )
        )

    def to_events(self) -> tuple[FSEvent, ...]:
        """Convert a SnapshotDiff into a sequence of FSEvents."""
        events: list[FSEvent] = []
        events.extend(
            [
                FSEvent(
                    src_path=src_path,
                    change=change,
                    is_directory=is_dir,
                    is_cover=is_cover,
                )
                for attr, change, is_dir, is_cover in _DIFF_FIELD_EVENT_MAP
                for src_path in getattr(self, attr)
            ]
        )
        events.extend(
            [
                FSEvent(
                    src_path=src_path,
                    change=FSChange.moved,
                    is_directory=is_dir,
                    is_cover=is_cover,
                    dest_path=dest_path,
                )
                for attr, is_dir, is_cover in _DIFF_MOVED_FIELD_EVENT_MAP
                for src_path, dest_path in getattr(self, attr)
            ]
        )
        return tuple(events)

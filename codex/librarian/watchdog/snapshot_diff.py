"""
Compute the diff between two snapshots.

Replaces watchdog's DirectorySnapshotDiff with a standalone implementation
that supports inode-based move detection and optional device-ignoring for
Docker/complex filesystems.
"""

from dataclasses import dataclass

from codex.librarian.watchdog.snapshot import Snapshot


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
        *,
        ignore_device: bool,
        inode_only_modified: bool,
    ) -> None:
        """Compute the diff between ref (old/database) and snapshot (new/disk)."""
        self._ignore_device = ignore_device
        self._inode_only_modified = inode_only_modified

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
        self.dirs_modified = [p for p in data.modified if ref.is_dir(p)]
        self.dirs_moved = [(f, t) for f, t in data.moved if ref.is_dir(f)]

        dir_added_set = set(self.dirs_added)
        dir_deleted_set = set(self.dirs_deleted)
        dir_modified_set = set(self.dirs_modified)
        dir_moved_set = set(self.dirs_moved)

        self.files_added = list(data.added - dir_added_set)
        self.files_deleted = list(data.deleted - dir_deleted_set)
        self.files_modified = list(data.modified - dir_modified_set)
        self.files_moved = list(data.moved - dir_moved_set)

    def _get_inode(self, snapshot: Snapshot, path: str):
        """Get inode, optionally ignoring device."""
        result = snapshot.inode(path)
        if self._ignore_device:
            return result[0]
        return result

    def _is_inode_equal(self, data: _DiffData, path: str) -> bool:
        """Return whether inodes match between ref and snapshot."""
        return self._get_inode(data.ref, path) == self._get_inode(data.snapshot, path)

    def _is_stats_equal(self, data: _DiffData, old_path: str, new_path: str) -> bool:
        """Return whether mtime and size match."""
        return data.ref.mtime(old_path) == data.snapshot.mtime(
            new_path
        ) and data.ref.size(old_path) == data.snapshot.size(new_path)

    def _check_unchanged_for_inode_changes(self, data: _DiffData) -> None:
        """Check unchanged paths for inode changes (file replaced in-place)."""
        for path in data.unchanged:
            if not self._is_inode_equal(data, path):
                if self._inode_only_modified:
                    data.modified.add(path)
                else:
                    data.added.add(path)
                    data.deleted.add(path)

    def _find_moved_paths(self, data: _DiffData) -> None:
        """Detect moves by matching inodes between deleted and added sets."""
        for old_path in tuple(data.deleted):
            inode = self._get_inode(data.ref, old_path)
            if new_path := data.snapshot.path(inode):
                data.deleted.remove(old_path)
                data.moved.add((old_path, new_path))

        for new_path in tuple(data.added):
            inode = self._get_inode(data.snapshot, new_path)
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

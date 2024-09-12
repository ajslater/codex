"""Custom directory snapshots."""

from dataclasses import dataclass

from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff


@dataclass
class SnapshotDiffData:
    """Temporary store for calculating data."""

    ref: DirectorySnapshot
    snapshot: DirectorySnapshot
    created: set
    deleted: set
    modified: set
    moved: set
    unchanged: frozenset


class CodexDirectorySnapshotDiff(DirectorySnapshotDiff):
    """Custom Diff allows inode only changes to be 'modified'."""

    def _get_inode(self, snapshot, full_path):
        """Get inode optionally ignoring device stats."""
        result = snapshot.inode(full_path)
        if self._ignore_device:
            result = result[0]
        return result

    def _is_inode_equal(self, data, path):
        """Return if the inodes are equal."""
        return self._get_inode(data.ref, path) == self._get_inode(data.snapshot, path)

    def _is_stats_equal(self, data, old_path, new_path):
        """Return if the mtime and size are equal.

        For old paths in the ref and new paths in the snapshot.
        """
        return data.ref.mtime(old_path) == data.snapshot.mtime(
            new_path
        ) and data.ref.size(old_path) == data.snapshot.size(new_path)

    def _check_unchanged_paths_for_inode_changes(self, data):
        """Check that all unchanged paths have the same inode."""
        for path in data.unchanged:
            if not self._is_inode_equal(data, path):
                if self._inode_only_modified:
                    data.modified.add(path)
                else:
                    # Add these to created and deleted. But...
                    # The _find_moved_paths() inode tracker should
                    #  sort them out.
                    # This is the same as in upstream dirsnapshot.py
                    data.created.add(path)
                    data.deleted.add(path)

    def _find_moved_paths(self, data):
        """Find moved paths in deleted and created."""
        for old_path in tuple(data.deleted):
            inode = self._get_inode(data.ref, old_path)
            if new_path := data.snapshot.path(inode):
                # file is not deleted but moved
                data.deleted.remove(old_path)
                data.moved.add((old_path, new_path))

        for new_path in tuple(data.created):
            inode = self._get_inode(data.snapshot, new_path)
            if old_path := data.ref.path(inode):
                data.created.remove(new_path)
                data.moved.add((old_path, new_path))

    def _find_modified_paths(self, data):
        """Find modified paths."""
        # first paths that have not moved
        for path in data.unchanged:
            if self._is_inode_equal(data, path) and not self._is_stats_equal(
                data, path, path
            ):
                data.modified.add(path)

        # Check moved paths for modificiations.
        for old_path, new_path in data.moved:
            if not self._is_stats_equal(data, old_path, new_path):
                data.modified.add(new_path)

    def __init__(  # C901, PLR0912
        self, ref, snapshot, ignore_device=False, inode_only_modified=False
    ):
        """Create diff object."""
        self._ignore_device = ignore_device
        self._inode_only_modified = inode_only_modified
        data = SnapshotDiffData(
            ref,
            snapshot,
            set(snapshot.paths - ref.paths),  # created
            set(ref.paths - snapshot.paths),  # deleted
            set(),  # modified
            set(),  # moved
            frozenset(ref.paths & snapshot.paths),  # unchanged
        )

        self._check_unchanged_paths_for_inode_changes(data)
        self._find_moved_paths(data)
        self._find_modified_paths(data)

        self._dirs_created = [path for path in data.created if snapshot.isdir(path)]
        self._dirs_deleted = [path for path in data.deleted if ref.isdir(path)]
        self._dirs_modified = [path for path in data.modified if ref.isdir(path)]
        self._dirs_moved = [(frm, to) for (frm, to) in data.moved if ref.isdir(frm)]

        self._files_created = list(data.created - set(self._dirs_created))
        self._files_deleted = list(data.deleted - set(self._dirs_deleted))
        self._files_modified = list(data.modified - set(self._dirs_modified))
        self._files_moved = list(data.moved - set(self._dirs_moved))

        # Release memory
        data = None

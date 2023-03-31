"""Custom directory snapshots."""
from watchdog.utils.dirsnapshot import DirectorySnapshotDiff


class CodexDirectorySnapshotDiff(DirectorySnapshotDiff):
    """Custom Diff allows inode only changes to be 'modified'."""

    def __init__(  # noqa C901, PLR0912
        self, ref, snapshot, ignore_device=False, inode_only_modified=False
    ):
        """Create diff object."""
        created = snapshot.paths - ref.paths
        deleted = ref.paths - snapshot.paths

        if ignore_device:

            def get_inode(directory, full_path):
                return directory.inode(full_path)[0]

        else:

            def get_inode(directory, full_path):
                return directory.inode(full_path)

        # check that all unchanged paths have the same inode
        modified = set()
        for path in ref.paths & snapshot.paths:
            if get_inode(ref, path) != get_inode(snapshot, path):
                if inode_only_modified:
                    modified.add(path)
                else:
                    created.add(path)
                    deleted.add(path)

        # find moved paths
        moved = set()
        for path in set(deleted):
            inode = ref.inode(path)
            new_path = snapshot.path(inode)
            if new_path:
                # file is not deleted but moved
                deleted.remove(path)
                moved.add((path, new_path))

        for path in set(created):
            inode = snapshot.inode(path)
            old_path = ref.path(inode)
            if old_path:
                created.remove(path)
                moved.add((old_path, path))

        # find modified paths
        # first check paths that have not moved
        for path in ref.paths & snapshot.paths:
            if get_inode(ref, path) == get_inode(snapshot, path):  # noqa SIM102
                if ref.mtime(path) != snapshot.mtime(path) or ref.size(
                    path
                ) != snapshot.size(path):
                    modified.add(path)

        for old_path, new_path in moved:
            if ref.mtime(old_path) != snapshot.mtime(new_path) or ref.size(
                old_path
            ) != snapshot.size(new_path):
                modified.add(old_path)

        self._dirs_created = [path for path in created if snapshot.isdir(path)]
        self._dirs_deleted = [path for path in deleted if ref.isdir(path)]
        self._dirs_modified = [path for path in modified if ref.isdir(path)]
        self._dirs_moved = [(frm, to) for (frm, to) in moved if ref.isdir(frm)]

        self._files_created = list(created - set(self._dirs_created))
        self._files_deleted = list(deleted - set(self._dirs_deleted))
        self._files_modified = list(modified - set(self._dirs_modified))
        self._files_moved = list(moved - set(self._dirs_moved))

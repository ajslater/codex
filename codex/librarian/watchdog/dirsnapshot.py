"""Custom directory snapshots."""
import os
from itertools import chain
from pathlib import Path

from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff

from codex.logger_base import LoggerBaseMixin
from codex.models import Comic, FailedImport, Folder


class CodexDatabaseSnapshot(DirectorySnapshot, LoggerBaseMixin):
    """Take snapshots from the Codex database."""

    MODELS = (Folder, Comic, FailedImport)

    @classmethod
    def _walk(cls, root):
        """Populate the DirectorySnapshot structures from the database."""
        for model in cls.MODELS:
            yield model.objects.filter(library__path=root).values("path", "stat")

    def _create_stat_from_db_stat(self, wp, stat_func, force):
        """Handle null or zeroed out database stat entries."""
        stat = wp.get("stat")
        if not stat or len(stat) != 10 or not stat[1]:
            path = Path(wp.get("path"))
            # Ensure valid params
            if path.exists():
                self.log.debug(f"Force modify path with bad db record: {path}")
                stat = list(stat_func(path))
                # Fake mtime will trigger a modified event
                stat[8] = 0.0
            else:
                self.log.debug(f"Force delete path with bad db record: {path}")
                # This will trigger a deleted event
                stat = Comic.ZERO_STAT

        if force:
            # Fake mtime will trigger modified event
            stat[8] = 0.0
        st = os.stat_result(tuple(stat))
        return st

    def _set_lookups(self, path, st):
        """Populate the lookup dirs."""
        self._stat_info[path] = st
        i = (st.st_ino, st.st_dev)
        self._inode_to_path[i] = path

    def __init__(
        self,
        path,
        _recursive=True,  # unused, always recursive
        stat=os.stat,
        _listdir=os.listdir,  # unused for database
        force=False,
        log_queue=None,
    ):
        """Initialize like DirectorySnapshot but use a database walk."""
        self.init_logger(log_queue)
        self._stat_info = {}
        self._inode_to_path = {}
        if not Path(path).is_dir():
            self.log.warning(f"{path} not found, cannot snapshot.")
            return

        # Add the library root
        root_stat = stat(path)
        self._set_lookups(path, root_stat)

        for wp in chain.from_iterable(self._walk(path)):
            st = self._create_stat_from_db_stat(wp, stat, force)
            self._set_lookups(wp["path"], st)


class CodexDirectorySnapshotDiff(DirectorySnapshotDiff):
    """Custom Diff allows inode only changes to be 'modified'."""

    def __init__(self, ref, snapshot, ignore_device=False, inode_only_modified=False):
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
            if get_inode(ref, path) == get_inode(snapshot, path):
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

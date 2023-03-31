"""Custom directory snapshots."""
import os
from itertools import chain
from pathlib import Path

from watchdog.utils.dirsnapshot import DirectorySnapshot

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
        if not stat or len(stat) != 10 or not stat[1]:  # noqa PLR2004
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
        return os.stat_result(tuple(stat))

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

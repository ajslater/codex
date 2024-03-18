"""Watched Path models."""

from pathlib import Path

from django.db.models import CASCADE, CharField, ForeignKey, JSONField

from codex.models.base import MAX_NAME_LEN
from codex.models.groups import BrowserGroupModel
from codex.models.library import MAX_PATH_LEN, Library

__all__ = ("WatchedPath", "Folder", "FailedImport")


class WatchedPath(BrowserGroupModel):
    """A filesystem path with data for Watchdog."""

    library = ForeignKey(Library, on_delete=CASCADE, db_index=True)
    path = CharField(max_length=MAX_PATH_LEN, db_index=True)
    stat = JSONField(null=True)
    parent_folder = ForeignKey(
        "Folder",
        on_delete=CASCADE,
        null=True,
    )
    ZERO_STAT = (0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0)

    def set_stat(self):
        """Set select stat params from the filesystem."""
        st_record = Path(self.path).stat()
        # Converting os.stat directly to a list or tuple saves
        # mtime as an int and causes problems.
        st = list(self.ZERO_STAT)
        st[0] = st_record.st_mode
        st[1] = st_record.st_ino
        # st[2] = st_record.st_dev is ignored by diff
        # st[3] = st_record.st_nlink
        # st[4] = st_record.st_uid
        # st[5] = st_record.st_gid
        st[6] = st_record.st_size
        # st[7] = st_record.st_atime
        st[8] = st_record.st_mtime
        self.stat = st

    def __str__(self):
        """Return the full path."""
        return self.path

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("library", "path")
        abstract = True


class Folder(WatchedPath):
    """File system folder."""


class FailedImport(WatchedPath):
    """Failed Comic Imports. Displayed in Admin Panel."""

    def set_reason(self, exc):
        """Can't do this in save() because it breaks update_or_create."""
        reason = str(exc)
        suffixes = (f": {self.path}", f": {self.path!r}")
        for suffix in suffixes:
            reason = reason.removesuffix(suffix)
        reason = reason[:MAX_NAME_LEN]
        self.name = reason.strip()

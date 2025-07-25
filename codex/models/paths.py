"""Watched Path models."""

from pathlib import Path
from types import MappingProxyType

from django.db.models import CASCADE, CharField, ForeignKey, JSONField, TextChoices
from typing_extensions import override

from codex.models.base import MAX_NAME_LEN, MAX_PATH_LEN, BaseModel, max_choices_len
from codex.models.fields import CleaningCharField
from codex.models.library import Library
from codex.models.util import get_sort_name

__all__ = ("CustomCover", "FailedImport")


class WatchedPath(BaseModel):
    """A filesystem path with data for Watchdog."""

    library = ForeignKey(Library, on_delete=CASCADE, db_index=True)
    parent_folder: ForeignKey | None = ForeignKey(
        "Folder",
        on_delete=CASCADE,
        null=True,
    )
    path = CleaningCharField(max_length=MAX_PATH_LEN, db_index=True)
    stat = JSONField(null=True)
    ZERO_STAT = (0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0)

    def set_stat(self):
        """Set select stat params from the filesystem."""
        path = Path(str(self.path))
        st_record = path.stat()
        # Converting os.stat directly to a list or tuple saves
        # mtime as an int and causes problems.
        st = list(self.ZERO_STAT)
        st[0] = st_record.st_mode
        st[1] = st_record.st_ino
        # st[2] = st_record.st_dev is ignored by diff
        # st[3] = st_record.st_nlink ignored
        # st[4] = st_record.st_uid ignored
        # st[5] = st_record.st_gid ignored
        st[6] = st_record.st_size
        # st[7] = st_record.st_atime ignored
        st[8] = st_record.st_mtime
        self.stat = st

    @override
    def presave(self):
        """Save stat."""
        self.set_stat()

    @override
    def __repr__(self):
        """Return the full path."""
        return str(self.path)

    class Meta(BaseModel.Meta):
        """Use Mixin Meta."""

        unique_together = ("library", "path")
        abstract = True

    def search_path(self) -> str:
        """Relative path for search index."""
        return self.path.removeprefix(self.library.path)


class FailedImport(WatchedPath):
    """Failed Comic Imports. Displayed in Admin Panel."""

    name = CharField(db_index=True, max_length=MAX_NAME_LEN, default="")

    def set_reason(self, exc):
        """Can't do this in save() because it breaks update_or_create."""
        reason = str(exc)
        suffixes = (f": {self.path}", f": {self.path!r}")
        for suffix in suffixes:
            reason = reason.removesuffix(suffix)
        reason = reason[:MAX_NAME_LEN]
        self.name = reason.strip()


class CustomCover(WatchedPath):
    """Custom Cover Image."""

    class GroupChoice(TextChoices):
        """Reading direction choices."""

        P = "p"
        I = "i"  # noqa: E741
        S = "s"
        A = "a"
        F = "f"

    FOLDER_COVER_STEM = ".codex-cover"
    DIR_GROUP_CHOICE_MAP = MappingProxyType(
        {
            "publishers": GroupChoice.P.value,
            "imprints": GroupChoice.I.value,
            "series": GroupChoice.S.value,
            "story-arcs": GroupChoice.A.value,
        }
    )

    parent_folder: ForeignKey | None = None
    group = CharField(
        max_length=max_choices_len(GroupChoice),
        db_index=True,
        choices=GroupChoice.choices,
    )
    sort_name = CharField(
        max_length=MAX_NAME_LEN, db_index=True, default="", db_collation="nocase"
    )

    def _set_group_and_sort_name(self):
        """Set group and sort_name from path."""
        path = Path(self.path)
        stem = path.stem
        if stem == self.FOLDER_COVER_STEM:
            self.group = self.GroupChoice.F.value
        else:
            self.group = self.DIR_GROUP_CHOICE_MAP[path.parent.name]
            self.sort_name = get_sort_name(stem)

    @override
    def presave(self):
        """Presave group and sort_name."""
        super().presave()
        self._set_group_and_sort_name()

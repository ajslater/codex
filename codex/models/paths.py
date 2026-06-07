"""Watched Path models."""

from pathlib import Path
from types import MappingProxyType
from typing import override

from django.db.models import CASCADE, CharField, ForeignKey, JSONField, TextChoices

from codex.models.base import MAX_NAME_LEN, MAX_PATH_LEN, BaseModel
from codex.models.choices import max_choices_len
from codex.models.library import Library
from codex.models.util import get_sort_name

__all__ = ("CustomCover", "FailedImport")


class WatchedPath(BaseModel):
    """A filesystem path with data for Watcher diffs."""

    library = ForeignKey(Library, on_delete=CASCADE, db_index=True)
    parent_folder: ForeignKey | None = ForeignKey(
        "Folder",
        on_delete=CASCADE,
        null=True,
    )
    path = CharField(max_length=MAX_PATH_LEN, db_index=True)
    stat = JSONField(null=True)
    ZERO_STAT = (0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0)

    def set_stat(self) -> None:
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
    def presave(self) -> None:
        """Save stat."""
        self.set_stat()

    @override
    def __repr__(self) -> str:
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

    def set_reason(self, exc) -> None:
        """Can't do this in save() because it breaks update_or_create."""
        reason = str(exc)
        suffixes = (f": {self.path}", f": {self.path!r}")
        for suffix in suffixes:
            reason = reason.removesuffix(suffix)
        reason = reason[:MAX_NAME_LEN].strip()
        if not reason:
            # Some exceptions stringify to empty (or to just the path, stripped
            # above). Fall back to the exception class name so a failed import
            # always records some reason rather than a blank.
            reason = type(exc).__name__
        self.name = reason


class CustomCover(WatchedPath):
    """Custom Cover Image."""

    class CollectionChoices(TextChoices):
        """Browse collections a custom cover may attach to (collection vocabulary)."""

        PUBLISHERS = "publishers"
        IMPRINTS = "imprints"
        SERIES = "series"
        VOLUMES = "volumes"
        ARCS = "arcs"
        FOLDERS = "folders"

    FOLDER_COVER_STEM = ".codex-cover"
    # On-disk directory name (user-facing filesystem convention) → collection.
    DIR_COLLECTION_CHOICE_MAP = MappingProxyType(
        {
            "publishers": CollectionChoices.PUBLISHERS.value,
            "imprints": CollectionChoices.IMPRINTS.value,
            "series": CollectionChoices.SERIES.value,
            "story-arcs": CollectionChoices.ARCS.value,
        }
    )

    parent_folder: ForeignKey | None = None
    # Override base to allow null. Custom covers no longer belong to any
    # library — every row is created via the upload endpoint with
    # ``library=None``. Kept on the column rather than dropped to avoid
    # a more invasive schema rewrite for the abstract ``WatchedPath``
    # inheritance.
    library = ForeignKey(  # pyright: ignore[reportIncompatibleUnannotatedOverride]
        Library, on_delete=CASCADE, db_index=True, null=True
    )
    collection = CharField(
        max_length=max_choices_len(CollectionChoices),
        db_index=True,
        choices=CollectionChoices.choices,
    )
    sort_name = CharField(
        max_length=MAX_NAME_LEN, db_index=True, default="", db_collation="nocase"
    )

    def _set_collection_and_sort_name(self) -> None:
        """Derive collection and sort_name from path (legacy filesystem-watch flow)."""
        # New uploads set ``collection`` and ``sort_name`` explicitly before
        # save() — no derivation needed.
        from codex.settings import CUSTOM_COVERS_UPLOADS_DIR

        path = Path(self.path)
        try:
            path.relative_to(CUSTOM_COVERS_UPLOADS_DIR)
        except ValueError:
            pass
        else:
            return
        stem = path.stem
        if stem == self.FOLDER_COVER_STEM:
            collection = self.CollectionChoices.FOLDERS.value
        else:
            collection = self.DIR_COLLECTION_CHOICE_MAP[path.parent.name]
            self.sort_name = get_sort_name(stem)
        self.collection = collection

    @override
    def presave(self) -> None:
        """Presave collection and sort_name."""
        super().presave()
        self._set_collection_and_sort_name()

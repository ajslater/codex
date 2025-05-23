"""Browser Group models."""

from django.db.models import CASCADE, SET_DEFAULT, ForeignKey
from typing_extensions import override

from codex.models.base import MAX_NAME_LEN, BaseModel
from codex.models.fields import CleaningCharField, CoercingPositiveSmallIntegerField
from codex.models.paths import CustomCover, WatchedPath
from codex.models.util import get_sort_name

__all__ = ("BrowserGroupModel", "Folder", "Imprint", "Publisher", "Series", "Volume")


class BrowserGroupModel(BaseModel):
    """Browser groups."""

    DEFAULT_NAME: str | None = ""
    PARENT: str = ""

    name = CleaningCharField(
        db_index=True, max_length=MAX_NAME_LEN, default=DEFAULT_NAME
    )
    sort_name = CleaningCharField(
        db_index=True,
        max_length=MAX_NAME_LEN,
        default=DEFAULT_NAME,
        db_collation="nocase",
    )
    custom_cover: ForeignKey | None = ForeignKey(
        CustomCover, on_delete=SET_DEFAULT, null=True, default=None
    )

    def set_sort_name(self):
        """Create sort_name for model."""
        self.sort_name = get_sort_name(self.name)

    @override
    def presave(self):
        """Set computed values."""
        self.set_sort_name()

    @override
    def save(self, *args, **kwargs):
        """Save computed fields."""
        self.presave()
        super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        """Without this a real table is created and joined to."""

        abstract = True


class Publisher(BrowserGroupModel):
    """The publisher of the comic."""

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name",)


class Imprint(BrowserGroupModel):
    """A Publishing imprint."""

    PARENT: str = "publisher"

    publisher = ForeignKey(Publisher, on_delete=CASCADE)

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name", "publisher")


class Series(BrowserGroupModel):
    """The series the comic belongs to."""

    PARENT: str = "imprint"

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    volume_count = CoercingPositiveSmallIntegerField(null=True)

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name", "imprint")
        verbose_name_plural = "Series"


class Volume(BrowserGroupModel):
    """The volume of the series the comic belongs to."""

    DEFAULT_NAME: str | None = None
    PARENT: str = "series"
    YEAR_LEN = 4

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    series = ForeignKey(Series, on_delete=CASCADE)
    issue_count = CoercingPositiveSmallIntegerField(null=True)
    name = CoercingPositiveSmallIntegerField(  # pyright: ignore[reportIncompatibleUnannotatedOverride]
        db_index=True, null=True, default=DEFAULT_NAME
    )

    # Harmful because name is numeric
    sort_name = None  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    custom_cover = None

    @override
    def set_sort_name(self):
        """Noop."""

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name", "series")

    @classmethod
    def to_str(cls, name):
        """Represent volume as a string."""
        if name is None:
            rep = ""
        else:
            name = str(name)
            rep = f"({name})" if len(name) == cls.YEAR_LEN else "v" + name
        return rep

    @override
    def __str__(self):
        """Represent volume as a string."""
        return self.to_str(self.name)


class WatchedPathBrowserGroup(BrowserGroupModel, WatchedPath):
    """Watched Path Browser Group."""

    @override
    def presave(self):
        """Fix multiple inheritance presave."""
        super().presave()
        WatchedPath.presave(self)

    class Meta(BrowserGroupModel.Meta, WatchedPath.Meta):
        """Use Mixin Meta."""

        abstract = True


class Folder(WatchedPathBrowserGroup):
    """File system folder."""

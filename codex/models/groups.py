"""Browser Group models."""

from django.db.models import CASCADE, SET_DEFAULT, ForeignKey
from typing_extensions import override

from codex.models.base import MAX_NAME_LEN, BaseModel
from codex.models.fields import CleaningCharField, CoercingPositiveSmallIntegerField
from codex.models.identifier import Identifier
from codex.models.paths import CustomCover, WatchedPath
from codex.models.util import get_sort_name

__all__ = (
    "BrowserGroupModel",
    "Folder",
    "IdentifiedBrowserGroupModel",
    "Imprint",
    "Publisher",
    "Series",
    "Volume",
)


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

    def _repr_parts(self) -> tuple[str, ...]:
        return (self.name,)

    @override
    def __repr__(self):
        """Represent as string."""
        return "/".join(self._repr_parts())


class IdentifiedBrowserGroupModel(BrowserGroupModel):
    """
    Identified Browser Group Model.

    Comicbox objects can have multiple identifiers, but if I let BrowserGroups have them
    then it would impossible to unlink a second level m2m relationship when comics are
    deleted. So I choose the highest priority one in import.
    Additionally, Browser groups will update to the highest priority identifier by
    source instead of creating duplicate groups to keep the hierarchy consolidated.
    """

    identifier = ForeignKey(Identifier, on_delete=CASCADE, null=True)

    class Meta(BrowserGroupModel.Meta):
        """Without this a real table is created and joined to."""

        abstract = True


class Publisher(IdentifiedBrowserGroupModel):
    """The publisher of the comic."""

    class Meta(IdentifiedBrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name",)


class Imprint(IdentifiedBrowserGroupModel):
    """A Publishing imprint."""

    PARENT: str = "publisher"

    publisher = ForeignKey(Publisher, on_delete=CASCADE)

    class Meta(IdentifiedBrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("publisher", "name")

    @override
    def _repr_parts(self):
        return (self.publisher.name, self.name)


class Series(IdentifiedBrowserGroupModel):
    """The series the comic belongs to."""

    PARENT: str = "imprint"

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    volume_count = CoercingPositiveSmallIntegerField(null=True)

    class Meta(IdentifiedBrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("imprint", "name")
        verbose_name_plural = "Series"

    @override
    def _repr_parts(self):
        return (
            self.publisher.name,
            self.imprint.name,
            self.name,
        )


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
    number_to = CoercingPositiveSmallIntegerField(
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

        unique_together = ("series", "name", "number_to")

    @classmethod
    def to_str(cls, number: int | None, number_to: int | None):
        """Represent volume as a string."""
        if number is None:
            rep = ""
        else:
            number_str = str(number)
            is_year = len(number_str) == cls.YEAR_LEN
            numbers_strs = (number_str, str(number_to))
            numbers_str = "-".join(numbers_strs)
            rep = f"({numbers_str})" if is_year else f"v{numbers_str}"
        return rep

    @override
    def _repr_parts(self):
        """Represent volume as a string."""
        return (
            self.publisher.name,
            self.imprint.name,
            self.series.name,
            self.to_str(self.name, self.number_to),
        )


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

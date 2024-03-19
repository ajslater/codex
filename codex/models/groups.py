"""Browser Group models."""

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    PositiveSmallIntegerField,
    SmallIntegerField,
)

from codex.models.base import MAX_NAME_LEN, BaseModel

__all__ = ("BrowserGroupModel", "Publisher", "Imprint", "Series", "Volume")


class BrowserGroupModel(BaseModel):
    """Browser groups."""

    DEFAULT_NAME = ""
    ORDERING = ("name", "pk")

    name = CharField(db_index=True, max_length=MAX_NAME_LEN, default=DEFAULT_NAME)

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

    ORDERING = ("publisher__name", "name", "pk")

    publisher = ForeignKey(Publisher, on_delete=CASCADE)

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name", "publisher")


class Series(BrowserGroupModel):
    """The series the comic belongs to."""

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    volume_count = PositiveSmallIntegerField(null=True)

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name", "imprint")
        verbose_name_plural = "Series"


class Volume(BrowserGroupModel):
    """The volume of the series the comic belongs to."""

    DEFAULT_NAME = None
    ORDERING = ("series__name", "name", "pk")
    YEAR_LEN = 4

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    series = ForeignKey(Series, on_delete=CASCADE)
    issue_count = PositiveSmallIntegerField(null=True)
    name = SmallIntegerField(db_index=True, null=True, default=DEFAULT_NAME)

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name", "series")

    @classmethod
    def to_str(cls, name):
        """Represent volume as a string."""
        if name in (None, ""):
            return ""

        name = str(name)
        return f"({name})" if len(name) == cls.YEAR_LEN else "v" + name

    def __str__(self):
        """Represent volume as a string."""
        return self.to_str(self.name)

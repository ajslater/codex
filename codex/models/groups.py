"""Browser Group models."""

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    PositiveSmallIntegerField,
    SmallIntegerField,
)

from codex.models.base import MAX_NAME_LEN, BaseModel
from codex.models.const import ARTICLES

__all__ = ("BrowserGroupModel", "Publisher", "Imprint", "Series", "Volume")


class BrowserGroupModel(BaseModel):
    """Browser groups."""

    DEFAULT_NAME = ""
    PARENT = ""

    name = CharField(db_index=True, max_length=MAX_NAME_LEN, default=DEFAULT_NAME)
    sort_name = CharField(db_index=True, max_length=MAX_NAME_LEN, default=DEFAULT_NAME)

    def set_sort_name(self):
        """Create sort_name for model."""
        lower_name = self.name.lower()
        sort_name = lower_name
        name_parts = lower_name.split()
        if len(name_parts) > 1:
            first_word = name_parts[0]
            if first_word in ARTICLES:
                sort_name = " ".join(name_parts[1:])
                sort_name += ", " + first_word
        self.sort_name = sort_name

    def presave(self):
        """Set computed values."""
        self.set_sort_name()

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

    PARENT = "publisher"

    publisher = ForeignKey(Publisher, on_delete=CASCADE)

    class Meta(BrowserGroupModel.Meta):
        """Constraints."""

        unique_together = ("name", "publisher")


class Series(BrowserGroupModel):
    """The series the comic belongs to."""

    PARENT = "imprint"

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
    PARENT = "series"
    YEAR_LEN = 4

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    series = ForeignKey(Series, on_delete=CASCADE)
    issue_count = PositiveSmallIntegerField(null=True)
    name = SmallIntegerField(db_index=True, null=True, default=DEFAULT_NAME)

    # Harmful because name is numeric
    sort_name = None

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

    def __str__(self):
        """Represent volume as a string."""
        return self.to_str(self.name)

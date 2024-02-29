"""Named models."""

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    PositiveIntegerField,
    URLField,
)

from codex.models.base import MAX_NAME_LEN, BaseModel
from codex.models.groups import BrowserGroupModel

__all__ = (
    "AgeRating",
    "Character",
    "ContributorPerson",
    "ContributorRole",
    "Contributor",
    "Country",
    "Genre",
    "Identifier",
    "IdentifierType",
    "Language",
    "Location",
    "OriginalFormat",
    "ScanInfo",
    "SeriesGroup",
    "Story",
    "StoryArc",
    "StoryArcNumber",
    "Tag",
    "Tagger",
    "Team",
)


class NamedModel(BaseModel):
    """A for simple named tables."""

    name = CharField(db_index=True, max_length=MAX_NAME_LEN)

    class Meta(BaseModel.Meta):
        """Defaults to uniquely named, must be overridden."""

        abstract = True
        unique_together = ("name",)

    def __str__(self):
        """Return the name."""
        return self.name


class AgeRating(NamedModel):
    """The Age Rating the comic was intended for."""


class Character(NamedModel):
    """A character that appears in the comic."""


class ContributorPerson(NamedModel):
    """Credited persons."""


class ContributorRole(NamedModel):
    """A role for the credited person. Writer, Inker, etc."""


class Contributor(BaseModel):
    """A contributor credit."""

    person = ForeignKey(ContributorPerson, on_delete=CASCADE)
    role = ForeignKey(ContributorRole, on_delete=CASCADE, null=True)

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("person", "role")


class Country(NamedModel):
    """The two letter country code."""

    class Meta(NamedModel.Meta):
        """Constraints."""

        verbose_name_plural = "Countries"


class Genre(NamedModel):
    """The genre the comic belongs to."""


class Language(NamedModel):
    """The two letter language code."""


class Location(NamedModel):
    """A location that appears in the comic."""


class OriginalFormat(NamedModel):
    """The original published format."""


class ScanInfo(NamedModel):
    """Whomever scanned the comic."""


class SeriesGroup(NamedModel):
    """A series group the series is part of."""


class Story(NamedModel):
    """A story in a commic."""

    class Meta(NamedModel.Meta):
        """Constraints."""

        verbose_name_plural = "Stories"


class StoryArc(NamedModel, BrowserGroupModel):
    """A story arc the comic is part of."""

    class Meta(NamedModel.Meta, BrowserGroupModel.Meta):
        """Fix Meta inheritance."""


class StoryArcNumber(BaseModel):
    """A story arc number the comic represents."""

    story_arc = ForeignKey(StoryArc, db_index=True, on_delete=CASCADE)
    number = PositiveIntegerField(null=True, default=None)

    class Meta(BaseModel.Meta):
        """Declare constraints and indexes."""

        unique_together = ("story_arc", "number")

    @property
    def name(self):
        """Provide a name to imitate a NamedModel."""
        suffix = f":{self.number}" if self.number is not None else ""
        return self.story_arc.name + suffix


class Tag(NamedModel):
    """Arbitrary Metadata Tag."""


class Tagger(NamedModel):
    """Tagger program."""


class Team(NamedModel):
    """A team that appears in the comic."""


class IdentifierType(NamedModel):
    """A type of identifier."""


class Identifier(BaseModel):
    """A method of identifying the comic."""

    identifier_type = ForeignKey(
        IdentifierType, db_index=True, on_delete=CASCADE, null=True
    )
    nss = CharField(max_length=MAX_NAME_LEN)
    url = URLField(default="")

    class Meta(BaseModel.Meta):
        """Declare constraints and indexes."""

        unique_together = ("identifier_type", "nss")

    @property
    def name(self):
        """Provide a name to imitate a NamedModel."""
        prefix = f"{self.identifier_type.name}:" if self.identifier_type else ""
        return prefix + self.nss

    def __str__(self):
        """Represent as a string."""
        return self.name + " " + self.url

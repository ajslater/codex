"""Named models."""

from django.db.models import (
    CASCADE,
    ForeignKey,
)
from typing_extensions import override

from codex.models.base import MAX_NAME_LEN, BaseModel, NamedModel
from codex.models.fields import CleaningCharField, CoercingPositiveSmallIntegerField
from codex.models.groups import BrowserGroupModel
from codex.models.identifier import Identifier

__all__ = (
    "AgeRating",
    "Character",
    "Country",
    "Credit",
    "CreditPerson",
    "CreditRole",
    "Genre",
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
    "Universe",
)


class IdentifiedNamedModel(NamedModel):
    """
    For NamedModels with Identifiers.

    Comicbox objects can have multiple identifiers, but if I let NamedModels have them
    then it would impossible to unlink a second level m2m relationship when comics are
    deleted. So I choose the highest priority one in import.
    """

    identifier = ForeignKey(Identifier, on_delete=CASCADE, null=True)

    class Meta(NamedModel.Meta):
        """Defaults to uniquely named, must be overridden."""

        abstract = True

    @override
    def __repr__(self):
        """Return the name."""
        suffix = ":" + str(self.identifier) if self.identifier else ""
        return self.name + suffix


class AgeRating(NamedModel):
    """The Age Rating the comic was intended for."""


class Character(IdentifiedNamedModel):
    """A character that appears in the comic."""


class CreditPerson(IdentifiedNamedModel):
    """Credited persons."""


class CreditRole(IdentifiedNamedModel):
    """A role for the credited person. Writer, Inker, etc."""


class Credit(BaseModel):
    """A credit."""

    person = ForeignKey(CreditPerson, on_delete=CASCADE)
    role = ForeignKey(CreditRole, on_delete=CASCADE, null=True)

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("person", "role")

    @override
    def __repr__(self):
        """Return the strings of parts."""
        return str(self.person) + ":" + str(self.role)


class Country(NamedModel):
    """The two letter country code."""

    class Meta(NamedModel.Meta):
        """Constraints."""

        verbose_name_plural = "Countries"


class Genre(IdentifiedNamedModel):
    """The genre the comic belongs to."""


class Language(NamedModel):
    """The two letter language code."""


class Location(IdentifiedNamedModel):
    """A location that appears in the comic."""


class OriginalFormat(NamedModel):
    """The original published format."""


class ScanInfo(NamedModel):
    """Whomever scanned the comic."""


class SeriesGroup(NamedModel):
    """A series group the series is part of."""


class Story(IdentifiedNamedModel):
    """A story in a commic."""

    class Meta(IdentifiedNamedModel.Meta):
        """Constraints."""

        verbose_name_plural = "Stories"


class StoryArc(IdentifiedNamedModel, BrowserGroupModel):
    """A story arc the comic is part of."""

    class Meta(IdentifiedNamedModel.Meta, BrowserGroupModel.Meta):
        """Fix Meta inheritance."""


class StoryArcNumber(BaseModel):
    """A story arc number the comic represents."""

    story_arc = ForeignKey(StoryArc, db_index=True, on_delete=CASCADE)
    number = CoercingPositiveSmallIntegerField(null=True, default=None)

    class Meta(BaseModel.Meta):
        """Declare constraints and indexes."""

        unique_together = ("story_arc", "number")

    @property
    def name(self):
        """Provide a name to imitate a NamedModel."""
        suffix = f":{self.number}" if self.number is not None else ""
        return self.story_arc.name + suffix


class Tag(IdentifiedNamedModel):
    """Arbitrary Metadata Tag."""


class Tagger(NamedModel):
    """Tagger program."""


class Team(IdentifiedNamedModel):
    """A team that appears in the comic."""


class Universe(IdentifiedNamedModel):
    """Universe the comic appears in."""

    designation = CleaningCharField(max_length=MAX_NAME_LEN)

    @override
    def __repr__(self):
        """Provide a name to imitate a NamedModel."""
        name = self.name + ":" + str(self.designation)
        if self.identifier:
            name += ":" + str(self.identifier)

        return name

"""Named models."""

from typing import override

from django.db.models import (
    CASCADE,
    SET_NULL,
    ForeignKey,
)

from codex.models.base import (
    MAX_FIELD_LEN,
    MAX_ISSUE_SUFFIX_LEN,
    MAX_NAME_LEN,
    BaseModel,
    NamedModel,
)
from codex.models.collections import BrowserCollectionModel, Volume
from codex.models.fields import (
    CleaningCharField,
    CoercingDecimalField,
    CoercingPositiveSmallIntegerField,
)
from codex.models.identifier import Identifier
from codex.models.util import parse_issue_parts

__all__ = (
    "Character",
    "Country",
    "Credit",
    "CreditPerson",
    "CreditRole",
    "Genre",
    "Language",
    "Location",
    "OriginalFormat",
    "Reprint",
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
    def __repr__(self) -> str:
        """Return the name."""
        suffix = ":" + str(self.identifier) if self.identifier else ""
        return self.name + suffix


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
    def __repr__(self) -> str:
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


class Reprint(BaseModel):
    """
    An alternate or localized edition of this issue.

    Denormalized on purpose: alternate series names must not become
    Series/Volume rows or they'd appear as phantom browser collections.
    ``series_name`` absorbs comicbox's ``series.sort_name`` when the
    reprint carries no ``series.name`` (MetronInfo AlternativeNames do
    this), so this is the only series string stored.
    """

    series_name = CleaningCharField(db_index=True, max_length=MAX_NAME_LEN)
    volume_number = CoercingPositiveSmallIntegerField(null=True, default=None)
    issue = CleaningCharField(max_length=MAX_FIELD_LEN, default="")
    language = CleaningCharField(max_length=MAX_FIELD_LEN, default="")
    identifier = ForeignKey(Identifier, on_delete=SET_NULL, null=True)
    # ``issue`` split into its sortable parts, mirroring
    # ``Comic.issue_number`` / ``issue_suffix``. Without them the
    # Alternate Series sort would order "#10" before "#2". Derived
    # in ``presave``, never imported directly; unindexed because they're
    # only read after an indexed join on pk or series_name.
    issue_number = CoercingDecimalField(decimal_places=2, max_digits=10, null=True)
    issue_suffix = CleaningCharField(
        max_length=MAX_ISSUE_SUFFIX_LEN,
        default="",
        db_collation="nocase",
    )

    class Meta(BaseModel.Meta):
        """Declare constraints and indexes."""

        unique_together = ("series_name", "volume_number", "issue", "language")

    @staticmethod
    def compose_name(
        series_name: str,
        volume_number: int | None = None,
        issue: str = "",
        language: str = "",
    ) -> str:
        """
        Compose a display name to imitate a NamedModel.

        Callers that only have the columns (browser filter choices, the
        table-view intersection) format through here so every label
        matches the metadata panel's.
        """
        parts = [series_name]
        if volume_number is not None:
            parts.append(Volume.to_str(volume_number, None))
        if issue:
            parts.append(f"#{issue}")
        if language:
            parts.append(f"({language})")
        return " ".join(parts)

    @property
    def name(self) -> str:
        """Compose a display name to imitate a NamedModel."""
        return self.compose_name(
            self.series_name, self.volume_number, self.issue, self.language
        )

    @override
    def presave(self) -> None:
        """Split ``issue`` into its sortable number and suffix."""
        super().presave()
        self.issue_number, self.issue_suffix = parse_issue_parts(self.issue)

    @override
    def save(self, *args, **kwargs) -> None:
        """
        Save computed fields.

        The importer's bulk create / update paths call ``presave``
        themselves, but direct ``save()`` callers (the tag editor, tests)
        would otherwise persist a row whose sort columns don't match its
        ``issue``.
        """
        self.presave()
        super().save(*args, **kwargs)


class ScanInfo(NamedModel):
    """Whomever scanned the comic."""


class SeriesGroup(NamedModel):
    """A series group the series is part of."""


class Story(IdentifiedNamedModel):
    """A story in a commic."""

    class Meta(IdentifiedNamedModel.Meta):
        """Constraints."""

        verbose_name_plural = "Stories"


class StoryArc(IdentifiedNamedModel, BrowserCollectionModel):
    """A story arc the comic is part of."""

    class Meta(IdentifiedNamedModel.Meta, BrowserCollectionModel.Meta):
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
    def __repr__(self) -> str:
        """Provide a name to imitate a NamedModel."""
        name = self.name + ":" + str(self.designation)
        if self.identifier:
            name += ":" + str(self.identifier)

        return name

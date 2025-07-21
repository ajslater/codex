"""Identifier Models."""

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    TextChoices,
    URLField,
)
from typing_extensions import override

from codex.models.base import MAX_NAME_LEN, BaseModel, NamedModel
from codex.models.fields import CleaningCharField

__all__ = ("Identifier", "IdentifierSource", "NamedModel")

_IDENTIFIER_TYPE_MAX_LENGTH = 16


class IdentifierSource(NamedModel):
    """A an Identifier's source."""


class IdentifierType(TextChoices):
    """
    The identifier type for the source.

    Values are table names.
    """

    ARC = "storyarc"
    CHARACTER = "character"
    GENRE = "genre"
    IMPRINT = "imprint"
    ISSUE = "comic"
    LOCATION = "location"
    PUBLISHER = "publisher"
    # REPRINT = "reprint" not yet implemented
    SERIES = "series"
    STORY = "story"
    TAG = "tag"
    TEAM = "team"
    UNIVERSE = "universe"
    ROLE = "creditrole"
    CREATOR = "creditperson"


class Identifier(BaseModel):
    """
    A method of identifying the comic.

    The only class with a url.
    """

    source = ForeignKey(IdentifierSource, db_index=True, on_delete=CASCADE, null=True)
    id_type = CharField(
        choices=IdentifierType.choices,
        db_index=True,
        max_length=_IDENTIFIER_TYPE_MAX_LENGTH,
    )
    key = CleaningCharField(max_length=MAX_NAME_LEN)
    url = URLField(default="")

    class Meta(BaseModel.Meta):
        """Declare constraints and indexes."""

        unique_together: tuple[str, ...] = ("source", "id_type", "key")

    @property
    def name(self):
        """Provide a urn like name to imitate a NamedModel."""
        source_name = f"{self.source.name}:" if self.source else ""
        parts = (source_name, self.id_type, self.key)
        return ":".join(parts)

    @override
    def __repr__(self):
        """Represent as a string."""
        return self.name + ":" + self.url

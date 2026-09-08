"""Identifier Models."""

from types import MappingProxyType
from typing import override

from bidict import frozenbidict
from comicbox.identifiers import DEFAULT_ID_TYPE
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    TextChoices,
    URLField,
)

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
    REPRINT = "reprint"
    SERIES = "series"
    STORY = "story"
    TAG = "tag"
    TEAM = "team"
    UNIVERSE = "universe"
    VOLUME = "volume"
    ROLE = "creditrole"
    CREATOR = "creditperson"


#: Codex names an identifier's type after the table it points at;
#: comicbox names it after the thing itself, so codex's ``storyarc`` is
#: comicbox's ``arc``. The two vocabularies agree member for member, so
#: the bridge is the enum's own member names: a type added to one side
#: cannot go missing from the other the way a second hand-written list
#: would. ``tests/test_identifier_types.py`` guards the agreement.
COMICBOX_ID_TYPE_MAP: frozenbidict[str, str] = frozenbidict(
    {id_type.value: id_type.name.lower() for id_type in IdentifierType}
)


def to_codex_id_type(comicbox_id_type: str | None) -> str:
    """
    Name the codex table a comicbox identifier type points at.

    An identifier states a type only when it isn't the one its position
    implies, so an absent type means the default: an issue.
    """
    if not comicbox_id_type:
        return IdentifierType.ISSUE.value
    return COMICBOX_ID_TYPE_MAP.inverse.get(
        comicbox_id_type.lower(), IdentifierType.ISSUE.value
    )


def to_comicbox_id_type(codex_id_type: str) -> str:
    """Name the comicbox identifier type for a codex table."""
    return COMICBOX_ID_TYPE_MAP.get(codex_id_type, DEFAULT_ID_TYPE)


#: What an identifier hanging on one of codex's tables names upstream,
#: where that differs from what the table itself is. A reprint's id is
#: the reprinted issue's id: the row is another edition of this book, and
#: the id names that edition's issue. No database publishes a page for a
#: "reprint", so reading the table name as the type built no link at all.
_POSITIONAL_ID_TYPE_OVERRIDES = MappingProxyType(
    {IdentifierType.REPRINT.value: DEFAULT_ID_TYPE}
)


def positional_id_type(codex_id_type: str) -> str:
    """
    Name the type an identifier on this codex table implies.

    An identifier states its type only when it differs from the one its
    position implies, so this is what to assume when none is stated. It
    is a question about the id, not about the row it hangs on, which is
    why it is not simply the table's own type.
    """
    override = _POSITIONAL_ID_TYPE_OVERRIDES.get(codex_id_type)
    return override or to_comicbox_id_type(codex_id_type)


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
    def name(self) -> str:
        """Provide a urn like name to imitate a NamedModel."""
        source_name = f"{self.source.name}:" if self.source else ""
        parts = (source_name, self.id_type, self.key)
        return ":".join(parts)

    @override
    def __repr__(self) -> str:
        """Represent as a string."""
        return self.name + ":" + self.url

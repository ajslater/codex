"""
Reading list documents: how codex stores comicbox's lists.

comicbox's model holds dates, Decimals and sets, so codex stores a list as
the JSON that comicbox itself writes, inner mapping only, and reads it back
through comicbox's own model loader. The tags source has no stored
document: it is built from the tag tables when it is needed.
"""

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from comicbox.exceptions import ReadingListError
from comicbox.readinglists import (
    ENTRIES_KEY,
    LIST_TYPE_KEY,
    NAME_KEY,
    NOTES_KEY,
    ORDERED_KEY,
    READING_LIST_KEY,
    SOURCE_KEY_KEY,
    SOURCE_KIND_KEY,
    SOURCES_KEY,
    ReadingListFormats,
    SourceKind,
    dumps,
)
from comicbox.readinglists.serialize import load_model

from codex.librarian.scribe.readinglists.arcs import one_arc_members, ordered_members
from codex.librarian.scribe.readinglists.references import comic_references
from codex.models import Comic, StoryArc
from codex.models.readinglist import ReadingListSource, ReadingListSourceKind

__all__ = (
    "COMICBOX_KINDS",
    "ENTRIES_KEY",
    "SOURCES_KEY",
    "STORY_LIST_TYPE",
    "TagsDocument",
    "check_format",
    "from_json",
    "tags_document",
    "to_json",
)

# Codex's source kind -> comicbox's: what a fetched or exported document
# calls where a list came from.
COMICBOX_KINDS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        ReadingListSourceKind.TAGS.value: SourceKind.TAGS.value,
        ReadingListSourceKind.UPLOAD.value: SourceKind.FILE.value,
        ReadingListSourceKind.URL.value: SourceKind.URL.value,
        ReadingListSourceKind.CATALOG.value: SourceKind.CATALOG.value,
        ReadingListSourceKind.METRON_LIST.value: SourceKind.METRON_LIST.value,
        ReadingListSourceKind.METRON_ARC.value: SourceKind.METRON_ARC.value,
        ReadingListSourceKind.COMICVINE_ARC.value: SourceKind.COMICVINE_ARC.value,
    }
)
# Lists from story-arc tags are comicbox's list type "story".
STORY_LIST_TYPE: Final = "story"
# An identifier source -> the comicbox kind of that database's own arc.
_ARC_POINTER_KINDS: Final = MappingProxyType(
    {"metron": SourceKind.METRON_ARC.value, "comicvine": SourceKind.COMICVINE_ARC.value}
)
# The document formats codex reads: ComicRack's. comicbox's own YAML and JSON
# reading list formats are not supported. Lists built from an online
# database's records have no document format.
_READ_FORMATS: Final = frozenset({ReadingListFormats.CBL, ReadingListFormats.JSON_CBL})
UNSUPPORTED_FORMAT: Final = "Only ComicRack .cbl and json-cbl reading lists are read."


def check_format(result) -> None:
    """Refuse a list read from a document in a format codex does not read."""
    if result.fmt is not None and result.fmt not in _READ_FORMATS:
        raise ReadingListError(UNSUPPORTED_FORMAT)


def to_json(reading_list: Mapping[str, Any]) -> dict[str, Any]:
    """Return a comicbox list as JSON-safe data, the inner mapping."""
    if not reading_list.get(ENTRIES_KEY) and not reading_list.get(NAME_KEY):
        return {}
    text = dumps(reading_list, ReadingListFormats.JSON)
    return json.loads(text)[READING_LIST_KEY]


def from_json(document: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return stored JSON as comicbox's model."""
    if not document:
        return {}
    return load_model(document)


@dataclass(slots=True)
class TagsDocument:
    """A tags source's list, and the comic each of its rows is."""

    document: dict[str, Any] = field(default_factory=dict)
    comics: list[int] = field(default_factory=list)


def _arc_pointers(sort_name: str) -> list[dict[str, str]]:
    """Point at the databases' own copies of the arc, the most common id first."""
    counts: defaultdict[tuple[str, str], int] = defaultdict(int)
    rows = StoryArc.objects.filter(
        sort_name=sort_name, identifier__isnull=False
    ).values_list("identifier__source__name", "identifier__key")
    for source, key in rows:
        if kind := _ARC_POINTER_KINDS.get(source):
            counts[(kind, key)] += 1
    pointers: dict[str, dict[str, str]] = {}
    for (kind, key), _count in sorted(counts.items(), key=lambda item: -item[1]):
        pointers.setdefault(kind, {SOURCE_KIND_KEY: kind, SOURCE_KEY_KEY: key})
    return list(pointers.values())


def tags_document(source: ReadingListSource) -> TagsDocument:
    """
    Build the tags source's list from the comics tagged with its arc.

    Every tagged comic is a row, even one whose reference is empty, so the
    list keeps it: such a row carries the comic's name as a note, joins
    nothing and stays its own entry.
    """
    members = ordered_members(one_arc_members(source.ref))
    pks = [pk for pk, _ in members]
    references = comic_references(pks)
    names = dict(Comic.objects.filter(pk__in=pks).values_list("pk", "name"))
    entries = []
    for pk in pks:
        reference = references.get(pk) or {NOTES_KEY: names.get(pk) or str(pk)}
        entries.append(reference)
    document: dict[str, Any] = {
        NAME_KEY: source.reading_list.name,
        LIST_TYPE_KEY: STORY_LIST_TYPE,
        SOURCES_KEY: [
            {SOURCE_KIND_KEY: SourceKind.TAGS.value},
            *_arc_pointers(source.ref),
        ],
        ENTRIES_KEY: entries,
    }
    if not source.ordered:
        document[ORDERED_KEY] = False
    return TagsDocument(document=document, comics=pks)

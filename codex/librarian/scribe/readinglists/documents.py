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
from typing import Any, Final

from comicbox.exceptions import ReadingListError
from comicbox.readinglists import ReadingListFormats, dumps
from comicbox.readinglists.serialize import load_model

from codex.librarian.scribe.readinglists.arcs import one_arc_members, ordered_members
from codex.librarian.scribe.readinglists.references import comic_references
from codex.models import Comic, StoryArc
from codex.models.readinglist import ReadingListSource

READING_LIST_KEY: Final = "reading_list"
ENTRIES_KEY: Final = "entries"
SOURCES_KEY: Final = "sources"
_ARC_POINTER_KINDS: Final = {"metron": "metron-arc", "comicvine": "comicvine-arc"}
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
    if not reading_list.get(ENTRIES_KEY) and not reading_list.get("name"):
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
        pointers.setdefault(kind, {"kind": kind, "key": key})
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
        reference = references.get(pk) or {"notes": names.get(pk) or str(pk)}
        entries.append(reference)
    document: dict[str, Any] = {
        "name": source.reading_list.name,
        "list_type": "story",
        SOURCES_KEY: [{"kind": "tags"}, *_arc_pointers(source.ref)],
        ENTRIES_KEY: entries,
    }
    if not source.ordered:
        document["ordered"] = False
    return TagsDocument(document=document, comics=pks)


def arc_pointer(source: ReadingListSource, kind: str) -> str | None:
    """Return the key of a database's copy of a tags source's arc."""
    for pointer in _arc_pointers(source.ref):
        if pointer["kind"] == kind:
            return pointer["key"]
    return None

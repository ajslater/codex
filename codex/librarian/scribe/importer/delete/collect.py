"""
Gather the collections a set of comics belongs to.

The browser's refresh probe reads a collection's *own* ``updated_at``,
not its comics', so any change to a comic's membership has to re-stamp
the collections it entered or left or the view never refreshes. The
delete phase needs this before it removes rows, and the poller's revival
pass needs the same shape after it clears a stamp, so it lives here
rather than on the importer class.
"""

from django.db.models import Prefetch

from codex.librarian.scribe.importer.const import (
    ALL_COMIC_COLLECTION_FIELD_NAMES,
    DIRECT_M2M_COLLECTION_FIELD_NAMES,
)
from codex.models import Comic, ReadingList, ReadingListEntry
from codex.settings import IMPORTER_DELETE_MAX_CHUNK_SIZE

# Story arcs browse as reading lists: a comic's arcs are the lists that
# hold it, story arc lists and every other list alike.
_ARCS_FIELD_NAME = "story_arc_numbers"


def init_comic_collection_map() -> dict:
    """Empty collection map, used later even when nothing changed."""
    collection_map = {}
    for field_name in ALL_COMIC_COLLECTION_FIELD_NAMES:
        if field_name == _ARCS_FIELD_NAME:
            related_model = ReadingList
        else:
            related_model = Comic._meta.get_field(field_name).related_model
        collection_map[related_model] = set()
    return collection_map


def _populate_one(collection_map, comic) -> None:
    for field_name in ALL_COMIC_COLLECTION_FIELD_NAMES:
        if field_name == _ARCS_FIELD_NAME:
            for entry in comic.reading_list_entries.all():
                collection_map[ReadingList].add(entry.reading_list_id)
        elif field_name in DIRECT_M2M_COLLECTION_FIELD_NAMES:
            related_model = comic._meta.get_field(field_name).related_model
            for obj in getattr(comic, field_name).only("pk"):
                collection_map[related_model].add(obj.pk)
        else:
            related_model = comic._meta.get_field(field_name).related_model
            related_id = getattr(comic, field_name).pk
            collection_map[related_model].add(related_id)


def populate_comic_collection_map(comic_qs, collection_map) -> None:
    """Add every collection the queryset's comics belong to."""
    entries = Prefetch(
        "reading_list_entries",
        queryset=ReadingListEntry.objects.only("comic_id", "reading_list_id"),
    )
    qs = comic_qs.only(*ALL_COMIC_COLLECTION_FIELD_NAMES).prefetch_related(
        entries, *DIRECT_M2M_COLLECTION_FIELD_NAMES
    )
    for comic in qs.iterator(chunk_size=IMPORTER_DELETE_MAX_CHUNK_SIZE):
        _populate_one(collection_map, comic)

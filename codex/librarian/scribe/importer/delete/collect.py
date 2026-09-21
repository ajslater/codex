"""
Gather the collections a set of comics belongs to.

The browser's refresh probe reads a collection's *own* ``updated_at``,
not its comics', so any change to a comic's membership has to re-stamp
the collections it entered or left or the view never refreshes. The
delete phase needs this before it removes rows, and the poller's revival
pass needs the same shape after it clears a stamp, so it lives here
rather than on the importer class.
"""

from codex.librarian.scribe.importer.const import (
    ALL_COMIC_COLLECTION_FIELD_NAMES,
    DIRECT_M2M_COLLECTION_FIELD_NAMES,
)
from codex.models import Comic, StoryArc
from codex.settings import IMPORTER_DELETE_MAX_CHUNK_SIZE


def init_comic_collection_map() -> dict:
    """Empty collection map, used later even when nothing changed."""
    collection_map = {}
    for field_name in ALL_COMIC_COLLECTION_FIELD_NAMES:
        if field_name == "story_arc_numbers":
            related_model = StoryArc
        else:
            related_model = Comic._meta.get_field(field_name).related_model
        collection_map[related_model] = set()
    return collection_map


def _populate_one(collection_map, comic) -> None:
    for field_name in ALL_COMIC_COLLECTION_FIELD_NAMES:
        if field_name == "story_arc_numbers":
            for san in comic.story_arc_numbers.select_related("story_arc").only(
                "story_arc"
            ):
                collection_map[StoryArc].add(san.story_arc.pk)
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
    qs = comic_qs.only(*ALL_COMIC_COLLECTION_FIELD_NAMES).prefetch_related(
        "story_arc_numbers__story_arc", *DIRECT_M2M_COLLECTION_FIELD_NAMES
    )
    for comic in qs.iterator(chunk_size=IMPORTER_DELETE_MAX_CHUNK_SIZE):
        _populate_one(collection_map, comic)

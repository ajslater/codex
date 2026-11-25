"""
Dump reading lists into the user-data sidecar.

Split out of :mod:`codex.user_data.dump`. Every list a person made,
imported or edited is kept: its header, its sources with their documents,
its entries with their comics by path and every hand edit. A global list
that only mirrors its story-arc tags is left out, since the tag sync
rebuilds it from the comics. The series mappings are kept too.

The restore lives in :mod:`codex.user_data.restore_reading_lists`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Final

from loguru import logger

from codex.user_data.identifiers import identifier_for_browse_collection

if TYPE_CHECKING:
    from codex.models.readinglist import (
        ReadingList,
        ReadingListEntry,
        ReadingListSeriesMapping,
        ReadingListSource,
    )
    from codex.user_data.store import SidecarStore

READING_LIST_TABLES: Final[tuple[str, ...]] = (
    "reading_lists",
    "reading_list_sources",
    "reading_list_entries",
    "reading_list_series_mappings",
)
_SERIES_COLLECTION: Final = "series"


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _datetime_str(value) -> str | None:
    return value.isoformat() if value else None


def kept_list_pks() -> set[int]:
    """
    Return the lists a backup must keep.

    Every list but a global one whose only sources are its tags, that is in
    tag order and that nobody edited. Read in bulk, not list by list: a
    library can have thousands of arcs.
    """
    from django.db.models import Q

    from codex.librarian.scribe.readinglists.sync import HAND_EDITED
    from codex.models.readinglist import (
        ReadingList,
        ReadingListEntry,
        ReadingListSource,
        ReadingListSourceKind,
    )

    tags = ReadingListSourceKind.TAGS
    kept = set(
        ReadingList.objects.filter(
            Q(user__isnull=False) | Q(order_locked=True)
        ).values_list("pk", flat=True)
    )
    kept |= set(
        ReadingList.objects.exclude(sources__kind=tags).values_list("pk", flat=True)
    )
    kept |= set(
        ReadingListSource.objects.exclude(kind=tags).values_list(
            "reading_list_id", flat=True
        )
    )
    kept |= set(
        ReadingListEntry.objects.filter(HAND_EDITED).values_list(
            "reading_list_id", flat=True
        )
    )
    kept |= {
        pk
        for pk, edited in ReadingList.objects.values_list("pk", "edited_fields")
        if edited
    }
    return kept


def serialize_reading_list(reading_list: ReadingList) -> dict[str, Any]:
    """Return a list's header row."""
    user = reading_list.user
    return {
        "uuid": str(reading_list.uuid),
        "username": user.username if user else "",
        "name": reading_list.name,
        "description": reading_list.description,
        "list_notes": reading_list.list_notes,
        "list_type": reading_list.list_type,
        "start_year": reading_list.start_year,
        "end_year": reading_list.end_year,
        "edited_fields": _json(reading_list.edited_fields or []),
        "order_locked": int(reading_list.order_locked),
        "extra": _json(reading_list.extra or {}),
        "updated_at": _datetime_str(reading_list.updated_at),
    }


def serialize_reading_list_source(
    list_uuid: str, source: ReadingListSource
) -> dict[str, Any]:
    """
    Return one source row, its document as JSON.

    A collection item is named by its identity; its revision, a digest of
    comic pks, means nothing in another database, so the first sync after a
    restore verifies it.
    """
    from codex.choices.readinglists import ReadingListSourceKind

    item = source.kind == ReadingListSourceKind.COLLECTION.value
    return {
        "list_uuid": list_uuid,
        "kind": source.kind,
        "ref": source.ref,
        "revision": "" if item else source.revision,
        "collection": source.collection,
        "position": source.position,
        "attribution_source": source.attribution_source,
        "attribution_url": source.attribution_url,
        "rank": source.rank,
        "ordered": int(source.ordered),
        "document": None if source.document is None else _json(source.document),
        "fetched_at": _datetime_str(source.fetched_at),
    }


def serialize_reading_list_entry(
    list_uuid: str,
    position: int,
    entry: ReadingListEntry,
    source_refs: dict[int, tuple[str, str]],
) -> dict[str, Any]:
    """Return one entry row: its comic by path, its sources by kind and ref."""
    comic = entry.comic
    sources = sorted(
        list(source_refs[pk]) for pk in entry.source_ids or () if pk in source_refs
    )
    return {
        "list_uuid": list_uuid,
        "position": position,
        "comic_path": str(comic.path) if comic else None,
        "reference": _json(entry.reference or {}),
        "series_name": entry.series_name,
        "issue": entry.issue,
        "year": entry.year,
        "match_tier": entry.match_tier,
        "needs_review": int(entry.needs_review),
        "ignored": int(entry.ignored),
        "manual": int(entry.manual),
        "entry_type": entry.entry_type,
        "sources": _json(sources),
    }


def serialize_series_mapping(mapping: ReadingListSeriesMapping) -> dict[str, Any]:
    """Return one series mapping, the series by its name chain."""
    parts = identifier_for_browse_collection(_SERIES_COLLECTION, mapping.series)
    return {
        "series_key": mapping.series_key,
        "year": mapping.year,
        "series_json": _json(parts),
    }


def _upsert(store: SidecarStore, table: str, keys: tuple[str, ...], data) -> bool:
    try:
        store.upsert(table, keys, data)
    except Exception:
        logger.exception(f"Sidecar dump upsert failed for {table!r}")
        return False
    return True


def _dump_lists(
    store: SidecarStore, kept: set[int], counts: dict[str, int]
) -> dict[int, str]:
    """Write the kept lists' headers; return their uuids by pk."""
    from codex.models.readinglist import ReadingList

    uuids: dict[int, str] = {}
    lists = ReadingList.objects.filter(pk__in=kept).select_related("user")
    for reading_list in lists.order_by("pk"):
        row = serialize_reading_list(reading_list)
        if _upsert(store, "reading_lists", ("uuid",), row):
            uuids[reading_list.pk] = row["uuid"]
            counts["reading_lists"] += 1
    return uuids


def _dump_sources(
    store: SidecarStore, uuids: dict[int, str], counts: dict[str, int]
) -> dict[int, tuple[str, str]]:
    """Write the kept lists' sources; return each source's (kind, ref) by pk."""
    from codex.models.readinglist import ReadingListSource

    refs: dict[int, tuple[str, str]] = {}
    sources = ReadingListSource.objects.filter(reading_list_id__in=uuids)
    for source in sources.order_by("reading_list_id", "rank", "pk"):
        list_uuid = uuids[source.reading_list_id]  # pyright: ignore[reportAttributeAccessIssue]
        row = serialize_reading_list_source(list_uuid, source)
        if _upsert(store, "reading_list_sources", ("list_uuid", "kind", "ref"), row):
            refs[source.pk] = (source.kind, source.ref)
            counts["reading_list_sources"] += 1
    return refs


# What ``serialize_reading_list_entry`` reads.
_ENTRY_FIELDS: Final = (
    "reading_list_id",
    "comic__path",
    "reference",
    "series_name",
    "issue",
    "year",
    "match_tier",
    "needs_review",
    "ignored",
    "manual",
    "entry_type",
    "source_ids",
)


def _dump_entries(
    store: SidecarStore,
    uuids: dict[int, str],
    refs: dict[int, tuple[str, str]],
    counts: dict[str, int],
) -> None:
    """Write the kept lists' entries, renumbered densely in list order."""
    from codex.models.readinglist import ReadingListEntry

    positions: defaultdict[int, int] = defaultdict(int)
    # Live entries are their items' comics: the sync writes them again.
    entries = ReadingListEntry.objects.filter(
        reading_list_id__in=uuids, live_source__isnull=True
    )
    # Of its comic an entry row keeps the path alone.
    for entry in (
        entries.select_related("comic")
        .only(*_ENTRY_FIELDS)
        .order_by("reading_list_id", "position", "pk")
    ):
        list_pk: int = entry.reading_list_id  # pyright: ignore[reportAttributeAccessIssue]
        row = serialize_reading_list_entry(
            uuids[list_pk], positions[list_pk], entry, refs
        )
        positions[list_pk] += 1
        if _upsert(store, "reading_list_entries", ("list_uuid", "position"), row):
            counts["reading_list_entries"] += 1


def _dump_mappings(store: SidecarStore, counts: dict[str, int]) -> None:
    from codex.models.readinglist import ReadingListSeriesMapping

    mappings = ReadingListSeriesMapping.objects.select_related(
        "series__publisher", "series__imprint"
    )
    for mapping in mappings.order_by("pk"):
        row = serialize_series_mapping(mapping)
        if _upsert(store, "reading_list_series_mappings", ("series_key", "year"), row):
            counts["reading_list_series_mappings"] += 1


def dump_reading_lists(store: SidecarStore) -> dict[str, int]:
    """Write the reading lists into the sidecar; return row counts per table."""
    counts: dict[str, int] = dict.fromkeys(READING_LIST_TABLES, 0)
    uuids = _dump_lists(store, kept_list_pks(), counts)
    refs = _dump_sources(store, uuids, counts)
    _dump_entries(store, uuids, refs, counts)
    _dump_mappings(store, counts)
    return counts

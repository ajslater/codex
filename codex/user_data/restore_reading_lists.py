"""
Restore reading lists from the user-data sidecar.

Split out of :mod:`codex.user_data.restore`, on the pattern of
:mod:`codex.user_data.restore_shelves`. A list is found by its UUID and
written back whole: its header, its sources and its entries replace what
the database holds for it, so a restore can run twice. An entry whose
comic is gone keeps its place without one and is matched again by its
reference.

A rebuilt database already holds a tags-only list for each story arc. A
restored list that carries the same arc as a source takes its place, so
one arc never feeds two lists.

Runs before the shelf items and saved filters, which find lists by UUID.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Final

from codex.user_data.restore_shelves import RestoreReport, has_table

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from sqlite3 import Row

    from codex.models.readinglist import ReadingList
    from codex.user_data.store import SidecarStore

_LISTS: Final = "reading_lists"
_MAPPINGS: Final = "reading_list_series_mappings"
_HEADER_TEXT: Final = ("description", "list_notes", "list_type")


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


def _grouped(store: SidecarStore, table: str) -> dict[str, list[Row]]:
    rows: defaultdict[str, list[Row]] = defaultdict(list)
    for row in store.fetchall(table):
        rows[row["list_uuid"]].append(row)
    return rows


def _owner(row: Row, report: RestoreReport):
    """Return the list's owner: None for a global list, False if gone."""
    from django.contrib.auth import get_user_model

    if not (username := row["username"]):
        return None
    user = get_user_model().objects.filter(username=username).first()
    if user is None:
        report.note_skipped(_LISTS, f"missing user {username!r}")
        return False
    return user


def _upsert_list(row: Row, user) -> ReadingList:
    """Write a list's header, creating it under its own UUID if it is gone."""
    from codex.librarian.scribe.readinglists.service import unique_name
    from codex.models.readinglist import ReadingList

    reading_list = ReadingList.objects.filter(uuid=row["uuid"]).first()
    if reading_list is None:
        reading_list = ReadingList(uuid=row["uuid"])
    name = row["name"]
    taken = ReadingList.objects.filter(user=user, name=name).exclude(uuid=row["uuid"])
    if user is not None and taken.exists():
        name = unique_name(name, user)
    reading_list.name = name
    reading_list.user = user
    for attr in _HEADER_TEXT:
        setattr(reading_list, attr, row[attr] or "")
    reading_list.start_year = row["start_year"]
    reading_list.end_year = row["end_year"]
    reading_list.edited_fields = _loads(row["edited_fields"], [])
    reading_list.order_locked = bool(row["order_locked"])
    reading_list.extra = _loads(row["extra"], {})
    reading_list.save()
    return reading_list


def _replace_sources(
    reading_list: ReadingList, rows: Sequence[Row]
) -> dict[tuple[str, str], int]:
    """Replace a list's sources; return each new source's pk by (kind, ref)."""
    from codex.models.readinglist import ReadingListSource

    ReadingListSource.objects.filter(reading_list=reading_list).delete()
    sources = ReadingListSource.objects.bulk_create(
        ReadingListSource(
            reading_list=reading_list,
            kind=row["kind"],
            ref=row["ref"],
            revision=row["revision"] or "",
            attribution_source=row["attribution_source"] or "",
            attribution_url=row["attribution_url"] or "",
            rank=row["rank"] or 0,
            ordered=bool(row["ordered"]),
            document=_loads(row["document"], None),
            fetched_at=row["fetched_at"],
        )
        for row in rows
    )
    return {(source.kind, source.ref): source.pk for source in sources}


def _release_arcs(reading_list: ReadingList, report: RestoreReport) -> None:
    """Delete the tags-only lists a rebuild made for this list's arcs."""
    from codex.librarian.scribe.readinglists.sync import is_tags_only
    from codex.models.readinglist import ReadingListSource, ReadingListSourceKind

    refs = ReadingListSource.objects.filter(
        reading_list=reading_list, kind=ReadingListSourceKind.TAGS
    ).values_list("ref", flat=True)
    others = (
        ReadingListSource.objects.filter(
            kind=ReadingListSourceKind.TAGS, ref__in=list(refs)
        )
        .exclude(reading_list=reading_list)
        .select_related("reading_list")
    )
    for source in others:
        other = source.reading_list
        if is_tags_only(other):
            other.delete()
        else:
            report.note_skipped(
                _LISTS, f"arc {source.ref!r} also feeds list {other.name!r}"
            )


def _comic_pk(path: str | None, cache: dict[str, int | None]) -> int | None:
    """Return the comic at a path, lowest pk first, or None if it is gone."""
    from codex.models import Comic

    if not path:
        return None
    if path not in cache:
        cache[path] = (
            Comic.objects.filter(path=path).order_by("pk").values_list("pk", flat=True)
        ).first()
    return cache[path]


def _entry(
    reading_list: ReadingList,
    row: Row,
    source_pks: dict[tuple[str, str], int],
    comic_pks: dict[str, int | None],
):
    from codex.models.readinglist import ReadingListEntry, ReadingListMatchTier

    comic_pk = _comic_pk(row["comic_path"], comic_pks)
    tier = row["match_tier"] or ""
    needs_review = bool(row["needs_review"])
    kept_tiers = (
        ReadingListMatchTier.MARKED_MISSING.value,
        ReadingListMatchTier.MANUAL.value,
    )
    if comic_pk is None and tier not in kept_tiers:
        # Its comic is gone: a rematch looks for it by its reference.
        tier = ReadingListMatchTier.NONE.value
        needs_review = False
    sources = [
        source_pks[(kind, ref)]
        for kind, ref in _loads(row["sources"], [])
        if (kind, ref) in source_pks
    ]
    return ReadingListEntry(
        reading_list=reading_list,
        position=row["position"],
        comic_id=comic_pk,
        reference=_loads(row["reference"], {}),
        series_name=row["series_name"] or "",
        issue=row["issue"] or "",
        year=row["year"],
        match_tier=tier,
        needs_review=needs_review,
        ignored=bool(row["ignored"]),
        manual=bool(row["manual"]),
        entry_type=row["entry_type"] or "",
        source_ids=sorted(sources),
    )


def _replace_entries(
    reading_list: ReadingList,
    rows: Sequence[Row],
    source_pks: dict[tuple[str, str], int],
    report: RestoreReport,
) -> None:
    from codex.models.readinglist import ReadingListEntry

    ReadingListEntry.objects.filter(reading_list=reading_list).delete()
    comic_pks: dict[str, int | None] = {}
    entries = [
        _entry(reading_list, row, source_pks, comic_pks)
        for row in sorted(rows, key=lambda row: row["position"])
    ]
    ReadingListEntry.objects.bulk_create(entries)
    for row in rows:
        if row["comic_path"] and comic_pks.get(row["comic_path"]) is None:
            report.note_skipped(
                "reading_list_entries",
                f"missing comic {row['comic_path']!r}, kept as a missing issue",
            )


def _restore_one_list(
    row: Row,
    sources: Sequence[Row],
    entries: Sequence[Row],
    report: RestoreReport,
) -> None:
    from django.db import transaction

    user = _owner(row, report)
    if user is False:
        return
    with transaction.atomic():
        reading_list = _upsert_list(row, user)
        source_pks = _replace_sources(reading_list, sources)
        _release_arcs(reading_list, report)
        _replace_entries(reading_list, entries, source_pks, report)
    report.note_written(_LISTS)


def _restore_mappings(
    store: SidecarStore, report: RestoreReport, resolve_pks: Callable, *, dry_run: bool
) -> None:
    from codex.models import Series
    from codex.models.readinglist import ReadingListSeriesMapping

    for row in store.fetchall(_MAPPINGS):
        if dry_run:
            report.note_written(_MAPPINGS)
            continue
        parts = _loads(row["series_json"], [])
        series_pks = resolve_pks("series", parts, Series) if parts else ()
        if not series_pks:
            report.note_skipped(_MAPPINGS, f"missing series {parts!r}")
            continue
        ReadingListSeriesMapping.objects.update_or_create(
            series_key=row["series_key"],
            year=row["year"] or 0,
            defaults={"series_id": series_pks[0]},
        )
        report.note_written(_MAPPINGS)


def restore_reading_lists(
    store: SidecarStore, report: RestoreReport, resolve_pks: Callable, *, dry_run: bool
) -> None:
    """Restore reading lists and series mappings; a backup without them is fine."""
    if not has_table(store, _LISTS):
        return
    sources = _grouped(store, "reading_list_sources")
    entries = _grouped(store, "reading_list_entries")
    for row in store.fetchall(_LISTS):
        if dry_run:
            report.note_written(_LISTS)
            continue
        uuid = row["uuid"]
        _restore_one_list(row, sources.get(uuid, []), entries.get(uuid, []), report)
    _restore_mappings(store, report, resolve_pks, dry_run=dry_run)

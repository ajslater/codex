"""
Resolve a backup's Reading Lists filter to the lists in this database.

Split out of :mod:`codex.user_data.restore`. A filter names its lists by
uuid. A list made from tags alone is not backed up, so after a rebuild the
tag sync made it again under a new uuid, and only its tags ref finds it. An
older backup's story arc filter names arcs, which are lists now.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codex.user_data.restore_shelves import RestoreReport


def _story_arc_list_pks(row_keys, row) -> list[int]:
    """
    Resolve an old backup's story-arc filter to the global lists of its names.

    Story arcs and reading lists are one concept now, so a filter on an arc
    is a filter on the arc's list. Of several global lists of one name the
    first made is the one the tags built.
    """
    from codex.models.readinglist import ReadingList

    if "story_arcs" not in row_keys:
        return []
    names = json.loads(row["story_arcs"] or "[]")
    first: dict[str, int] = {}
    rows = (
        ReadingList.objects.filter(user__isnull=True, name__in=names)
        .order_by("pk")
        .values_list("name", "pk")
    )
    for name, pk in rows:
        first.setdefault(name, pk)
    return [first[name] for name in names if name in first]


def _list_tags(row_keys, row) -> dict[str, str]:
    """Return the backup's tags ref of each filtered list holding tags, by uuid."""
    if "reading_list_tags" not in row_keys:
        return {}
    refs = json.loads(row["reading_list_tags"] or "{}")
    return refs if isinstance(refs, dict) else {}


def _tags_list_pk(ref: str, visible) -> int | None:
    """
    Return the list now holding the tags ``ref``: one made from them alone.

    A list from tags alone is not backed up, so after a rebuild the tag
    sync made it again under a new uuid; its tags source still has the ref.
    """
    from codex.librarian.scribe.readinglists.sync import is_tags_only
    from codex.models.readinglist import ReadingList, ReadingListSourceKind

    holders = list(
        ReadingList.objects.filter(
            visible, sources__kind=ReadingListSourceKind.TAGS, sources__ref=ref
        )
        .distinct()
        .order_by("pk")
    )
    tags_only = (holder.pk for holder in holders if is_tags_only(holder))
    return next(tags_only, holders[0].pk if holders else None)


def resolve_filter_reading_lists(
    row_keys, row, browser, report: RestoreReport
) -> list[int]:
    """
    Resolve reading list uuids to the pks of lists the owner may see.

    A uuid that finds no list falls back to the list's tags ref; one that
    finds nothing either is reported, as an unmatched tag name is.
    """
    from codex.models.readinglist import ReadingList
    from codex.views.auth import GroupACLMixin

    uuids = (
        [str(uuid) for uuid in json.loads(row["reading_lists"] or "[]")]
        if "reading_lists" in row_keys
        else []
    )
    visible = GroupACLMixin.reading_list_visibility_filter(browser.user)
    found = {
        str(uuid): pk
        for uuid, pk in ReadingList.objects.filter(visible, uuid__in=uuids).values_list(
            "uuid", "pk"
        )
    }
    tags = _list_tags(row_keys, row)
    pks: list[int] = []
    for uuid in uuids:
        pk = found.get(uuid)
        if pk is None and (ref := tags.get(uuid)):
            pk = _tags_list_pk(ref, visible)
        if pk is None:
            report.note_skipped(
                "settings_filters",
                f"dropped reading list {uuid} unmatched for {browser.user.username}",
            )
            continue
        pks.append(pk)
    return list(dict.fromkeys([*pks, *_story_arc_list_pks(row_keys, row)]))

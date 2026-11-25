"""
A reading list's missing issues, placed among the page's comics.

Inside one list, in Reading Order, with no search or filter, the issues the
library lacks show as placeholders at their places. Everyone who sees the
list sees them: a missing issue has no comic to hide.

A page owns the list positions after the previous page's last comic,
through its own last comic. The first page starts at the list's start and
the last runs to its end; reversed order mirrors it. The comics' positions
are read the way the browser orders them, first place forward and last
place reversed, and paginated the way the browser pages them, so the two
agree on where a page ends.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from django.core.paginator import EmptyPage, Paginator
from django.db.models import Max, Min

from codex.models.readinglist import MISSING_Q, ReadingListEntry
from codex.views.readinglists.access import shown_entries_q

READING_ORDER: Final = "story_arc_number"


@dataclass(frozen=True, slots=True)
class PageBounds:
    """
    The positions a page owns, in the page's own order.

    ``after`` is the previous page's last comic, excluded; ``through`` is
    this page's last comic, included. None is open: the list's start on
    the first page, its end on the last.
    """

    after: int | None = None
    through: int | None = None


def comic_positions(acl, user, list_pk: int, *, reverse: bool) -> list[int]:
    """Return the list's comics' places, as the browser orders them."""
    place = Max if reverse else Min
    rows = (
        ReadingListEntry.objects.filter(
            shown_entries_q(acl, user), reading_list_id=list_pk, comic__isnull=False
        )
        .values("comic_id")
        .annotate(place=place("position"))
        .values_list("place", flat=True)
    )
    return sorted(rows, reverse=reverse)


def page_bounds(
    positions: Sequence[int], page: int, per_page: int, orphans: int
) -> PageBounds | None:
    """Return the positions page ``page`` owns, or None for no such page."""
    # With no comic to place them among, every missing issue is on page 1:
    # the paginator allows an empty first page and refuses the rest.
    paginator = Paginator(positions, per_page, orphans=orphans)
    try:
        this_page = paginator.page(page)
    except EmptyPage:
        return None
    after = paginator.page(page - 1).object_list[-1] if page > 1 else None
    through = this_page.object_list[-1] if this_page.has_next() else None
    return PageBounds(after=after, through=through)


def _owns(position: int, bounds: PageBounds, *, reverse: bool) -> bool:
    if reverse:
        return (bounds.after is None or position < bounds.after) and (
            bounds.through is None or position >= bounds.through
        )
    return (bounds.after is None or position > bounds.after) and (
        bounds.through is None or position <= bounds.through
    )


def _entry_repr(entry: ReadingListEntry) -> dict[str, Any]:
    return {
        "pk": entry.pk,
        "position": entry.position,
        "series_name": entry.series_name,
        "issue": entry.issue,
        "year": entry.year,
        "entry_type": entry.entry_type,
    }


def page_missing_entries(
    acl, user, list_pk: int, bounds: PageBounds | None, *, reverse: bool
) -> list[dict[str, Any]]:
    """Return the missing issues on the page, in page order."""
    missing = ReadingListEntry.objects.filter(
        shown_entries_q(acl, user), MISSING_Q, reading_list_id=list_pk
    ).order_by("-position" if reverse else "position", "pk")
    if bounds is None:
        return []
    return [
        _entry_repr(entry)
        for entry in missing.only(*_FIELDS)
        if _owns(entry.position, bounds, reverse=reverse)
    ]


_FIELDS: Final = ("pk", "position", "series_name", "issue", "year", "entry_type")

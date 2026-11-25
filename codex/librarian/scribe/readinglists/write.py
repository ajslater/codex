"""
Write a reading list into its comics' files, as a story arc.

Each matched comic gains the list's arc through comicbox's additive patch,
numbered by its first place in the list when the list has an order. The
comic's other arcs, tags and tag formats stay. Once the files are
imported again the arc tags make a tags source, which the tag sync
attaches to this list, by the mark left here, rather than to a new one.
"""

from dataclasses import dataclass, field
from typing import Any, Final

from comicbox.readinglists.arcs import arc_patch

from codex.models import StoryArc
from codex.models.readinglist import (
    DANGLING_Q,
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.models.util import get_sort_name

#: ``ReadingList.extra`` key: the sort name of the arc written for the list.
WRITTEN_ARC_KEY: Final = "written_arc"


@dataclass(frozen=True, slots=True)
class ArcWrite:
    """The arc a list is written as, and the patch for each of its comics."""

    name: str
    patches: dict[int, dict[str, Any]] = field(default_factory=dict)


def arc_name(reading_list: ReadingList) -> str:
    """Return the arc the list already has in tags, else the list's name."""
    ref = (
        ReadingListSource.objects.filter(
            reading_list=reading_list, kind=ReadingListSourceKind.TAGS
        )
        .values_list("ref", flat=True)
        .first()
    )
    if ref and (
        name := StoryArc.objects.filter(sort_name=ref)
        .order_by("pk")
        .values_list("name", flat=True)
        .first()
    ):
        return name
    return reading_list.name


def _is_ordered(reading_list: ReadingList) -> bool:
    """Return whether the list is locked, made by hand, or any source is ordered."""
    if reading_list.order_locked:
        return True
    sources = ReadingListSource.objects.filter(reading_list=reading_list)
    return not sources.exists() or sources.filter(ordered=True).exists()


def arc_write(reading_list: ReadingList) -> ArcWrite:
    """
    Build the patch for each matched comic of the list.

    A comic's number is its first place among the shown entries, missing
    ones included, so the numbers keep the list's gaps.
    """
    name = arc_name(reading_list)
    ordered = _is_ordered(reading_list)
    comic_pks = (
        ReadingListEntry.objects.filter(reading_list=reading_list, ignored=False)
        .exclude(DANGLING_Q)
        .order_by("position", "pk")
        .values_list("comic_id", flat=True)
    )
    numbers: dict[int, int | None] = {}
    for place, comic_pk in enumerate(comic_pks, start=1):
        if comic_pk is not None:
            numbers.setdefault(comic_pk, place if ordered else None)
    patches = {pk: arc_patch(name, number) for pk, number in numbers.items()}
    return ArcWrite(name=name, patches=patches)


def mark_written(reading_list: ReadingList, name: str) -> None:
    """
    Remember the arc, so the tags source it makes joins this list.

    A list that already has the arc as its tags source needs no mark: the
    sync updates that source.
    """
    sort_name = get_sort_name(name)
    if ReadingListSource.objects.filter(
        reading_list=reading_list, kind=ReadingListSourceKind.TAGS, ref=sort_name
    ).exists():
        return
    reading_list.extra = {
        **reading_list.extra,
        WRITTEN_ARC_KEY: sort_name,
    }
    reading_list.save(update_fields=("extra", "updated_at"))


def written_lists() -> dict[str, ReadingList]:
    """Map the sort names of arcs written but not yet seen to their lists."""
    lists = ReadingList.objects.filter(
        user__isnull=True, extra__has_key=WRITTEN_ARC_KEY
    ).order_by("pk")
    return {
        str(reading_list.extra[WRITTEN_ARC_KEY]).casefold(): reading_list
        for reading_list in lists
    }

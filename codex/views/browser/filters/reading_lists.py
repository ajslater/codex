"""
The reading lists filter: comics in the lists the viewer may see.

Every query here goes through the list-visibility helper, so another
user's personal list pk matches nothing, and its comics never count as
"in a list" for the None choice.
"""

from collections.abc import Mapping
from typing import Any, Final

from django.db.models import Exists, F, OuterRef, Q, QuerySet

from codex.models import Comic, ReadingListEntry
from codex.views.readinglists.access import list_kind_q, visible_lists

READING_LISTS_FILTER: Final = "reading_lists"
# Picks lists, not comics: Mine, Curated, From Tags.
READING_LIST_KIND_FILTER: Final = "reading_list_kind"
# Shelves folded into reading lists; a request still filtering by one gets
# nothing.
RETIRED_SHELVES_FILTER: Final = "shelves"
_IN_LISTS: Final = "reading_list_entries__reading_list__in"
_SHOWN: Final = "reading_list_entries__ignored"


def filters_within_a_list(filters: Mapping[str, Any]) -> dict[str, Any]:
    """
    Return the browser filters that apply to reading inside one list.

    The Reading List Kind picks lists, so inside one list it does nothing.
    The reader and Continue Reading both read through this, so Continue
    never offers a comic the reader then refuses.
    """
    return {
        key: value for key, value in filters.items() if key != READING_LIST_KIND_FILTER
    }


def listed_comics(user, pks=None, kinds=None) -> QuerySet[Comic]:
    """
    Return the comics shown in the user's visible lists.

    In the lists ``pks``, or in lists of any of ``kinds``, when given.
    """
    lists = visible_lists(user)
    if pks is not None:
        lists = lists.filter(pk__in=pks)
    if kinds is not None:
        lists = lists.filter(list_kind_q(kinds, user))
    return Comic.objects.filter(**{_IN_LISTS: lists.values("pk"), _SHOWN: False})


def listed_q(user, kinds=None) -> Exists:
    """
    Whether a comic is shown on a list the user sees, of any of ``kinds``.

    A correlated ``EXISTS`` per comic, for a probe that stops at the first
    row: :func:`listed_comics` gathers every listed comic first, which on a
    library of thousands of lists costs more than the whole probe.

    The list is tested as ``reading_list_id + 0``, which no index can key
    on. As a bare column, SQLite searched the comic-and-list index once per
    visible list for every comic: a reader sees every tags list, so two
    thousand seeks a comic made the reader's menu eight times slower. Now
    it seeks a comic's few entries and checks each against the lists.
    """
    lists = visible_lists(user)
    if kinds is not None:
        lists = lists.filter(list_kind_q(kinds, user))
    return Exists(
        ReadingListEntry.objects.filter(comic_id=OuterRef("pk"), ignored=False)
        .alias(_list_key=F("reading_list_id") + 0)
        .filter(_list_key__in=lists.values("pk"))
    )


def reading_lists_filter(
    rel_prefix: str, filter_list, user, *, match_all: bool = False
) -> Q:
    """
    Filter by membership in the chosen lists; None is "in no list".

    Under All, on every chosen list: one ``IN`` subquery per list, ANDed.
    A list the viewer may not see holds none of their comics, and None
    with a list matches nothing.
    """
    pks = [pk for pk in filter_list if pk is not None]
    match_none = len(pks) != len(filter_list)
    if match_all and pks:
        if match_none:
            return Q(pk__in=())
        query = Q()
        for pk in pks:
            query &= Q(**{f"{rel_prefix}pk__in": listed_comics(user, [pk])})
        return query
    query = Q()
    if pks:
        query |= Q(**{f"{rel_prefix}pk__in": listed_comics(user, pks)})
    if match_none:
        query |= ~Q(**{f"{rel_prefix}pk__in": listed_comics(user)})
    return query


def list_kind_filter(rel_prefix: str, kinds, user) -> Q:
    """
    Filter by membership in a visible list of any of ``kinds``.

    An ``IN`` subquery, never a join, so a comic on two such lists is one
    row and sums stay per comic.
    """
    return Q(**{f"{rel_prefix}pk__in": listed_comics(user, kinds=kinds)})


def held_lists_filter(filter_list, user, *, match_all: bool = False) -> Q:
    """
    At the lists root: the lists the chosen lists hold as items.

    Filtering the lists by a list shows what it holds, not every list
    that shares an issue with it. Under All, the lists every chosen list
    holds; a list the viewer may not see holds nothing, and None with a
    list matches nothing. A pk list, not a subquery, so cachalot sees the
    change when an item is added.
    """
    from codex.librarian.scribe.readinglists.live import COLLECTION_KIND
    from codex.models.readinglist import ReadingListSource

    pks = [pk for pk in filter_list if pk is not None]
    if match_all and len(pks) != len(filter_list):
        return Q(pk__in=())
    chosen = visible_lists(user).filter(pk__in=pks)
    rows = ReadingListSource.objects.filter(
        reading_list__in=list(chosen.values_list("pk", flat=True)),
        kind=COLLECTION_KIND,
        collection="arcs",
        target_id__isnull=False,
    ).values_list("reading_list_id", "target_id")
    if not match_all:
        return Q(pk__in=[target for _, target in rows])
    held_by: dict[int, set[int]] = {pk: set() for pk in pks}
    for list_pk, target in rows:
        held_by[list_pk].add(target)
    every = set.intersection(*held_by.values()) if held_by else set()
    return Q(pk__in=sorted(every))

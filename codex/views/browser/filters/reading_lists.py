"""
The reading lists filter: comics in the lists the viewer may see.

Every query here goes through the list-visibility helper, so another
user's personal list pk matches nothing, and its comics never count as
"in a list" for the None choice.
"""

from typing import Final

from django.db.models import Q, QuerySet

from codex.models import Comic
from codex.views.readinglists.access import list_kind_q, visible_lists

READING_LISTS_FILTER: Final = "reading_lists"
# Picks lists, not comics: Mine, Curated, From Tags.
READING_LIST_KIND_FILTER: Final = "reading_list_kind"
# Shelves folded into reading lists; a request still filtering by one gets
# nothing.
RETIRED_SHELVES_FILTER: Final = "shelves"
_IN_LISTS: Final = "reading_list_entries__reading_list__in"
_SHOWN: Final = "reading_list_entries__ignored"


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


def reading_lists_filter(rel_prefix: str, filter_list, user) -> Q:
    """Filter by membership in the chosen lists; None is "in no list"."""
    pks = [pk for pk in filter_list if pk is not None]
    query = Q()
    if pks:
        query |= Q(**{f"{rel_prefix}pk__in": listed_comics(user, pks)})
    if len(pks) != len(filter_list):
        query |= ~Q(**{f"{rel_prefix}pk__in": listed_comics(user)})
    return query


def list_kind_filter(rel_prefix: str, kinds, user) -> Q:
    """
    Filter by membership in a visible list of any of ``kinds``.

    An ``IN`` subquery, never a join, so a comic on two such lists is one
    row and sums stay per comic.
    """
    return Q(**{f"{rel_prefix}pk__in": listed_comics(user, kinds=kinds)})


def held_lists_filter(filter_list, user) -> Q:
    """
    At the lists root: the lists the chosen lists hold as items.

    Filtering the lists by a list shows what it holds, not every list
    that shares an issue with it. A pk list, not a subquery, so cachalot
    sees the change when an item is added.
    """
    from codex.librarian.scribe.readinglists.live import COLLECTION_KIND
    from codex.models.readinglist import ReadingListSource

    chosen = visible_lists(user).filter(
        pk__in=[pk for pk in filter_list if pk is not None]
    )
    held = ReadingListSource.objects.filter(
        reading_list__in=list(chosen.values_list("pk", flat=True)),
        kind=COLLECTION_KIND,
        collection="arcs",
        target_id__isnull=False,
    ).values_list("target_id", flat=True)
    return Q(pk__in=list(held))

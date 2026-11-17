"""
The reading lists filter: comics in the lists the viewer may see.

Every query here goes through the list-visibility helper, so another
user's personal list pk matches nothing, and its comics never count as
"in a list" for the None choice.
"""

from typing import Final

from django.db.models import Q, QuerySet

from codex.models import Comic, ReadingList
from codex.views.auth import GroupACLMixin

READING_LISTS_FILTER: Final = "reading_lists"
_IN_LISTS: Final = "reading_list_entries__reading_list__in"
_SHOWN: Final = "reading_list_entries__ignored"


def visible_lists(user) -> QuerySet:
    """Return the lists the user may see: global ones and their own."""
    return ReadingList.objects.filter(
        GroupACLMixin.reading_list_visibility_filter(user)
    )


def listed_comics(user, pks=None) -> QuerySet[Comic]:
    """Return the comics shown in the user's visible lists, or in ``pks``."""
    lists = visible_lists(user)
    if pks is not None:
        lists = lists.filter(pk__in=pks)
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

"""The reading lists a metadata selection is in."""

from typing import Any

from django.db.models import Count, Min, Q, QuerySet

from codex.models.readinglist import DANGLING_Q, ReadingListEntry
from codex.views.auth import GroupACLMixin


def _visible_entries(user) -> QuerySet:
    """Entries of lists the user may see that nobody hid, none dangling."""
    return ReadingListEntry.objects.filter(
        GroupACLMixin.reading_list_visibility_filter(user, "reading_list__"),
        ignored=False,
    ).exclude(DANGLING_Q)


def selection_reading_lists(
    user, comic_pks: QuerySet, *, single: bool, is_admin: bool
) -> list[dict[str, Any]]:
    """
    List the reading lists holding any of the selected comics.

    Each is ``{pk, name, position, count, editable}``: ``position`` is the
    comic's 1-based place among the list's shown entries (only for a single
    comic, at its first place), ``count`` the list's shown entries, missing
    ones included, and ``editable`` whether this user may change the list.
    """
    rows = tuple(
        _visible_entries(user)
        .filter(comic_id__in=comic_pks)
        .values("reading_list_id", "reading_list__name", "reading_list__user_id")
        .annotate(first=Min("position"))
        .order_by("reading_list__sort_name", "reading_list_id")
    )
    if not rows:
        return []
    list_pks = [row["reading_list_id"] for row in rows]
    counts = dict(
        _visible_entries(user)
        .filter(reading_list_id__in=list_pks)
        .values_list("reading_list_id")
        .annotate(count=Count("pk"))
        .order_by()
    )
    positions: dict[int, int] = {}
    if single:
        before = Q()
        for row in rows:
            before |= Q(
                reading_list_id=row["reading_list_id"], position__lt=row["first"]
            )
        positions = dict(
            _visible_entries(user)
            .filter(before)
            .values_list("reading_list_id")
            .annotate(count=Count("pk"))
            .order_by()
        )
    user_pk = user.pk if user is not None and user.is_authenticated else None
    return [
        {
            "pk": row["reading_list_id"],
            "name": row["reading_list__name"],
            "position": positions.get(row["reading_list_id"], 0) + 1
            if single
            else None,
            "count": counts.get(row["reading_list_id"], 0),
            "editable": is_admin
            if row["reading_list__user_id"] is None
            else row["reading_list__user_id"] == user_pk,
        }
        for row in rows
    ]

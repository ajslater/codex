"""Who may see and change a reading list, and which of its entries they see."""

from collections.abc import Iterable
from typing import Any, Final

from django.db.models import Exists, OuterRef, Q, QuerySet
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from codex.choices.browser import BROWSER_READING_LIST_KIND_CHOICES
from codex.models import Comic
from codex.models.readinglist import (
    ReadingList,
    ReadingListEntry,
    ReadingListSource,
    ReadingListSourceKind,
)
from codex.views.auth import AuthFilterGenericAPIView, GroupACLMixin

# The browser's Reading List Kind filter, in menu order.
LIST_KINDS: Final = tuple(BROWSER_READING_LIST_KIND_CHOICES)
MINE_LIST_KIND: Final = "mine"


def visible_lists(user) -> QuerySet:
    """Return the lists a user may see: global ones and their own."""
    return ReadingList.objects.filter(
        GroupACLMixin.reading_list_visibility_filter(user)
    )


def can_edit(user, reading_list: ReadingList) -> bool:
    """
    Whether ``user`` may change a list.

    A global list is an admin's to edit; a personal one is its owner's.
    """
    if user is None or not user.is_authenticated:
        return False
    if reading_list.user_id is None:  # pyright: ignore[reportAttributeAccessIssue]
        return bool(user.is_staff)
    return reading_list.user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]


def tags_only_q() -> Q:
    """
    Return the lists made from story-arc tags alone.

    A tags source and no other. ``Exists`` rather than a join, so a list
    is not repeated per source and cachalot sees the sources table.
    """
    sources = ReadingListSource.objects.filter(reading_list=OuterRef("pk"))
    tags = Exists(sources.filter(kind=ReadingListSourceKind.TAGS.value))
    other = Exists(sources.exclude(kind=ReadingListSourceKind.TAGS.value))
    return Q(tags) & ~Q(other)


def list_kind_q(kinds: Iterable[str], user) -> Q:
    """
    Return the lists of any of ``kinds``, the browser's Reading List Kind.

    The one definition of the kinds. Every list the viewer sees is exactly
    one kind, decided in this order: ``mine`` is the viewer's own lists,
    nothing for a viewer who is not signed in; ``tags`` is any other list
    made from story-arc tags alone; ``curated`` is every other list.
    Ownership can be given away, so a viewer may own a list from tags: it
    is Mine. An unknown kind matches nothing.
    """
    signed_in = user is not None and user.is_authenticated
    not_mine = ~Q(user=user) if signed_in else Q()
    query = Q(pk__in=())
    for kind in kinds:
        match kind:
            case "mine" if signed_in:
                query |= Q(user=user)
            case "tags":
                query |= tags_only_q() & not_mine
            case "curated":
                query |= ~tags_only_q() & not_mine
            case _:
                pass
    return query


def list_kinds_for(user) -> tuple[str, ...]:
    """Return the kinds a viewer may pick: no Mine for one not signed in."""
    if user is not None and user.is_authenticated:
        return LIST_KINDS
    return tuple(kind for kind in LIST_KINDS if kind != MINE_LIST_KIND)


def menu_lists_q(user) -> Q:
    """
    Return the lists a user's add-to-list menus offer.

    Their own lists and, for an admin, the global lists not made from tags
    alone: a list from tags follows its tags, and there is one per arc.
    """
    if user is None or not user.is_authenticated:
        return Q(pk__in=())
    q = Q(user=user)
    if user.is_staff:
        q |= Q(user__isnull=True) & ~tags_only_q()
    return q


def get_visible_list(user, pk: Any, *, edit: bool) -> ReadingList:
    """
    Return the list ``pk`` for a user who may see it, or may change it.

    A list the user may not see is indistinguishable from a missing one.
    """
    reading_list = visible_lists(user).filter(pk=pk).first()
    if reading_list is None:
        reason = "No such reading list."
        raise NotFound(reason)
    if edit and not can_edit(user, reading_list):
        reason = "You may not change this reading list."
        raise PermissionDenied(reason)
    return reading_list


def entries_acl_q(acl: GroupACLMixin, user) -> Q:
    """
    Return the entries whose comic, if any, ``user`` may see.

    A missing issue has no comic to hide, so everyone who sees the list
    sees it. An entry whose comic is hidden from the user is no part of
    the list for them, and a live entry whose comic went is no part of it
    for anyone.
    """
    comicless = Q(comic__isnull=True, live_source__isnull=True)
    return comicless | acl.get_acl_filter(ReadingListEntry, user)


def shown_entries_q(acl: GroupACLMixin, user) -> Q:
    """
    Return the entries of a list ``user`` sees: not hidden, comic visible.

    The one visibility rule for reading a list's entries: the entries
    view, export, copy, the details and the grid's missing issues.
    """
    return Q(ignored=False) & entries_acl_q(acl, user)


def to_pk(value: Any, what: str) -> int:
    """Read one pk from a request, or refuse it with a 400."""
    reason = f"{what} must be a number."
    if value is None or isinstance(value, bool):
        raise ValidationError(reason)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(reason) from exc


def to_pks(values: Any, what: str) -> list[int]:
    """Read a list of pks from a request, or refuse it with a 400."""
    if values is None:
        return []
    if isinstance(values, str | bytes) or not isinstance(values, Iterable):
        reason = f"{what} must be a list of numbers."
        raise ValidationError(reason)
    return [to_pk(value, what) for value in values]


class ReadingListAccessView(AuthFilterGenericAPIView):
    """Resolve the url's list for a viewer who may see it, or may change it."""

    def get_reading_list(self, *, edit: bool = True) -> ReadingList:
        """Return the list named by the url; changing it needs :func:`can_edit`."""
        return get_visible_list(self.request.user, self.kwargs["pk"], edit=edit)

    def shown_entries_q(self) -> Q:
        """Return the entries of a list this user sees."""
        return shown_entries_q(self, self.request.user)

    def visible_comic_pks(self, raw: Any) -> list[int]:
        """Read comic pks from a request, keeping the ones the user may see."""
        pks = to_pks(raw, "comics")
        acl = self.get_acl_filter(Comic, self.request.user)
        visible = set(
            Comic.objects.filter(acl, pk__in=pks).values_list("pk", flat=True)
        )
        return [pk for pk in pks if pk in visible]

    def data_value(self, key: str, default: Any = None) -> Any:
        """Read a request body value."""
        return self.request.data.get(key, default)

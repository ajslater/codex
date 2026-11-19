"""Who may see and change a reading list, and which of its entries they see."""

from collections.abc import Iterable
from typing import Any

from django.db.models import Q, QuerySet
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from codex.models import Comic
from codex.models.readinglist import ReadingList, ReadingListEntry
from codex.views.auth import AuthFilterGenericAPIView, GroupACLMixin


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


def entries_acl_q(acl: GroupACLMixin, user) -> Q:
    """
    Return the entries whose comic, if any, ``user`` may see.

    A missing issue has no comic to hide, so everyone who sees the list
    sees it. An entry whose comic is hidden from the user is no part of
    the list for them.
    """
    return Q(comic__isnull=True) | acl.get_acl_filter(ReadingListEntry, user)


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

    def visible_lists(self) -> QuerySet:
        """Return the lists this user may see: global ones and their own."""
        return ReadingList.objects.filter(
            self.reading_list_visibility_filter(self.request.user)
        )

    def get_reading_list(self, *, edit: bool = True) -> ReadingList:
        """
        Return the list named by the url.

        A list the user may not see is indistinguishable from a missing
        one. Changing it also needs :func:`can_edit`.
        """
        reading_list = self.visible_lists().filter(pk=self.kwargs["pk"]).first()
        if reading_list is None:
            reason = "No such reading list."
            raise NotFound(reason)
        if edit and not can_edit(self.request.user, reading_list):
            reason = "You may not change this reading list."
            raise PermissionDenied(reason)
        return reading_list

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

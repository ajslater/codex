"""Who may see and change a reading list."""

from typing import Any

from django.db.models import QuerySet
from rest_framework.exceptions import NotFound, PermissionDenied

from codex.models.readinglist import ReadingList
from codex.views.auth import AuthFilterGenericAPIView


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

    def data_value(self, key: str, default: Any = None) -> Any:
        """Read a request body value."""
        return self.request.data.get(key, default)

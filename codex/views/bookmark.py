"""Bookmark views."""

from rest_framework.response import Response
from rest_framework.views import APIView

from codex.models import Comic
from codex.serializers.metadata import UserBookmarkFinishedSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_base import BrowserBaseView
from codex.views.mixins import UserBookmarkMixin


class UserBookmarkFinishedView(BrowserBaseView, UserBookmarkMixin):
    """Mark read or unread recursively."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def patch(self, request, *args, **kwargs):
        """Mark read or unread recursively."""
        serializer = UserBookmarkFinishedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = self.kwargs.get("group")
        relation = self.GROUP_RELATION.get(group)
        pk = self.kwargs.get("pk")
        # Optimizing this call with only seems to fail the subsequent updates
        comics = Comic.objects.filter(**{relation: pk})
        updates = {"finished": serializer.validated_data.get("finished")}

        for comic in comics:
            # can't do this in bulk if using update_or_create withtout a
            # third party packages.
            self.update_user_bookmark(updates, comic=comic)

        return Response()


class ComicBookmarkView(APIView, UserBookmarkMixin):
    """Bookmark updater."""

    def patch(self, request, *args, **kwargs):
        """Save a user bookmark after a page change."""
        pk = self.kwargs.get("pk")
        page_num = self.kwargs.get("page_num")
        updates = {"bookmark": page_num}
        self.update_user_bookmark(updates, pk=pk)
        return Response()

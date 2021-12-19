"""Bookmark views."""

from rest_framework.response import Response
from stringcase import snakecase

from codex.models import Comic
from codex.serializers.bookmark import (
    ComicReaderSettingsSerializer,
    UserBookmarkFinishedSerializer,
)
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_base import BrowserBaseView
from codex.views.mixins import SessionMixin, UserBookmarkMixin


NULL_READER_SETTINGS = {
    "fitTo": None,
    "twoPages": None,
}


class UserBookmarkFinishedView(BrowserBaseView, UserBookmarkMixin):
    """Mark read or unread recursively."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def patch(self, request, *args, **kwargs):
        """Mark read or unread recursively."""
        serializer = UserBookmarkFinishedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = self.kwargs.get("group")
        relation = str(self.GROUP_RELATION.get(group))
        pk = self.kwargs.get("pk")
        # Optimizing this call with only seems to fail the subsequent updates
        comics = Comic.objects.filter(**{relation: pk})
        updates = {"finished": serializer.validated_data.get("finished")}

        for comic in comics:
            # can't do this in bulk if using update_or_create withtout a
            # third party packages.
            self.update_user_bookmark(updates, comic=comic)

        return Response()


class ComicBookmarkView(UserBookmarkMixin):
    """Bookmark updater."""

    def patch(self, request, *args, **kwargs):
        """Save a user bookmark after a page change."""
        pk = self.kwargs.get("pk")
        page = self.kwargs.get("page")
        updates = {"bookmark": page}
        self.update_user_bookmark(updates, pk=pk)
        return Response()


class ComicSettingsView(SessionMixin, UserBookmarkMixin):
    """Set Comic Settigns."""

    def validate(self, serializer):
        """Validate and translate the submitted data."""
        serializer.is_valid(raise_exception=True)
        # camel 2 snake
        snake_dict = {}
        for key, val in serializer.validated_data.items():
            snake_key = snakecase(key)
            snake_dict[snake_key] = val
        return snake_dict

    def patch(self, request, *args, **kwargs):
        """Patch the bookmark settings for one comic."""
        serializer = ComicReaderSettingsSerializer(data=self.request.data)
        snake_dict = self.validate(serializer)

        pk = self.kwargs.get("pk")
        self.update_user_bookmark(snake_dict, pk=pk)
        return Response()

    def put(self, request, *args, **kwargs):
        """Put the session settings for all comics."""
        serializer = ComicReaderSettingsSerializer(data=self.request.data)
        snake_dict = self.validate(serializer)
        # Default for all comics
        reader_session = self.get_session(self.READER_KEY)
        reader_session["defaults"] = snake_dict
        self.request.session.save()

        # Null out this comic's settings so it uses all comic defaults
        pk = self.kwargs.get("pk")
        self.update_user_bookmark(NULL_READER_SETTINGS, pk=pk)
        return Response()

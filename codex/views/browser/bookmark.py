"""Bookmark view."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.librarian.bookmark.update import BookmarkUpdate
from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.serializers.models.bookmark import (
    BookmarkFinishedSerializer,
    BookmarkSerializer,
)
from codex.views.bookmark import BookmarkAuthMixin
from codex.views.browser.filters.filter import BrowserFilterView

LOG = get_logger(__name__)


class BookmarkView(BookmarkUpdate, BookmarkAuthMixin, BrowserFilterView):
    """User Bookmark View."""

    serializer_class = BookmarkSerializer

    def _parse_params(self):
        """Validate and translate the submitted data."""
        group = self.kwargs.get("group")
        # If the target is recursive, strip everything but finished state data.
        serializer_class = None if group == "c" else BookmarkFinishedSerializer

        data = self.request.data
        if serializer_class:
            serializer = serializer_class(data=data, partial=True)
        else:
            serializer = self.get_serializer(data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def _get_comic_query(self):
        """Get comic pks for group."""
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        return self.get_filtered_queryset(Comic, group=group, pks=pks).only("pk")

    @extend_schema(request=serializer_class, responses=None)
    def patch(self, *_args, **_kwargs):
        """Update bookmarks recursively."""
        updates = self._parse_params()

        auth_filter = self.get_bookmark_auth_filter()
        comic_qs = self._get_comic_query()

        self.update_bookmarks(auth_filter, comic_qs, updates, LOG)
        return Response()

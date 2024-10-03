"""Bookmark views."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.librarian.bookmark.update import BookmarkUpdate
from codex.logger.logging import get_logger
from codex.serializers.models.bookmark import (
    BookmarkFinishedSerializer,
    BookmarkSerializer,
)
from codex.views.auth import (
    AuthFilterAPIView,
    AuthFilterGenericAPIView,
)
from codex.views.const import FILTER_ONLY_GROUP_RELATION

LOG = get_logger(__name__)


class BookmarkBaseView(AuthFilterAPIView):
    """Base class for Bookmark Views."""

    def get_bookmark_auth_filter(self):
        """Filter only the user's bookmarks."""
        if self.request.user.is_authenticated:
            key = "user_id"
            value = self.request.user.pk
        else:
            if not self.request.session or not self.request.session.session_key:
                LOG.debug("no session, make one")
                self.request.session.save()
            key = "session_id"
            value = self.request.session.session_key
        return {key: value}


class BookmarkView(AuthFilterGenericAPIView, BookmarkBaseView, BookmarkUpdate):
    """User Bookmark View."""

    serializer_class = BookmarkSerializer

    def _parse_params(self):
        """Validate and translate the submitted data."""
        group = self.kwargs.get("group")
        # If the target is recursive, strip everything but finished state data.
        serializer_class = None if group == "c" else BookmarkFinishedSerializer

        data = self.request.data  # type: ignore
        if serializer_class:
            serializer = serializer_class(data=data, partial=True)
        else:
            serializer = self.get_serializer(data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @extend_schema(request=serializer_class, responses=None)
    def patch(self, *_args, **_kwargs):
        """Update bookmarks recursively."""
        updates = self._parse_params()

        auth_filter = self.get_bookmark_auth_filter()

        group = self.kwargs.get("group")
        rel = FILTER_ONLY_GROUP_RELATION[group] + "__in"
        pks = self.kwargs.get("pks")
        comic_filter = {rel: pks}

        self.update_bookmarks(auth_filter, comic_filter, updates)
        return Response()

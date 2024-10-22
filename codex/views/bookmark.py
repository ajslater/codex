"""Views for reading comic books."""

from abc import ABC
from typing import TYPE_CHECKING

from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.views.auth import AuthAPIView

if TYPE_CHECKING:
    from codex.models import BrowserGroupModel

LOG = get_logger(__name__)


class BookmarkFilterMixin(APIView, ABC):
    """Bookmark filter methods."""

    def __init__(self, *args, **kwargs):
        """Initialize the bm_annotation_data."""
        super().__init__(*args, **kwargs)
        self._bm_rels: dict[BrowserGroupModel, str] = {}
        self._bm_filters: dict[BrowserGroupModel, Q] = {}

    def get_bm_rel(self, model):
        """Create bookmark relation."""
        if model not in self._bm_rels:
            rel_prefix = self.get_rel_prefix(model)  # type: ignore
            self._bm_rels[model] = rel_prefix + "bookmark"
        return self._bm_rels[model]

    def get_my_bookmark_filter(self, bm_rel):
        """Get a filter for my session or user defined bookmarks."""
        if self.request.user and self.request.user.is_authenticated:
            key = f"{bm_rel}__user"
            value = self.request.user
        else:
            key = f"{bm_rel}__session__session_key"
            value = self.request.session.session_key
        my_bookmarks_kwargs = {key: value}
        return Q(**my_bookmarks_kwargs)


class BookmarkAuthMixin(APIView):
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


class BookmarkPageView(BookmarkAuthMixin, AuthAPIView):
    """Display a comic page from the archive itself."""

    def _update_bookmark(self):
        """Update the bookmark if the bookmark param was passed."""
        auth_filter = self.get_bookmark_auth_filter()
        comic_pks = (self.kwargs.get("pk"),)
        page = self.kwargs.get("page")
        updates = {"page": page}

        task = BookmarkUpdateTask(auth_filter, comic_pks, updates)
        LIBRARIAN_QUEUE.put(task)

    def put(self, *_args, **_kwargs):
        """Get the comic page from the archive."""
        self._update_bookmark()
        return Response()

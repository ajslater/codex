"""Views for reading comic books."""

from abc import ABC
from typing import TYPE_CHECKING

from django.db.models.query_utils import Q
from rest_framework.response import Response

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.views.auth import AuthAPIView, AuthMixin, GroupACLMixin

if TYPE_CHECKING:
    from rest_framework.request import Request

    from codex.models import BrowserGroupModel


class BookmarkFilterMixin(GroupACLMixin, ABC):
    """Bookmark filter methods."""

    def init_bookmark_filter(self) -> None:
        """Initialize the bm_annotation_data."""
        if TYPE_CHECKING:
            self.request: Request
        self._bm_rels: dict[BrowserGroupModel, str] = {}
        self._bm_filters: dict[BrowserGroupModel, Q] = {}

    def get_bm_rel(self, model):
        """Create bookmark relation."""
        if model not in self._bm_rels:
            rel_prefix = self.get_rel_prefix(model)
            self._bm_rels[model] = rel_prefix + "bookmark"
        return self._bm_rels[model]

    def get_my_bookmark_filter(self, bm_rel) -> Q:
        """Get a filter for my session or user defined bookmarks."""
        if self.request.user and self.request.user.is_authenticated:
            key = f"{bm_rel}__user"
            value = self.request.user
        else:
            key = f"{bm_rel}__session"
            value = self.request.session.session_key
        my_bookmarks_kwargs = {key: value}
        return Q(**my_bookmarks_kwargs)


class BookmarkAuthMixin(AuthMixin):
    """Base class for Bookmark Views."""

    def get_bookmark_auth_filter(self) -> dict[str, int | str | None]:
        """Filter only the user's bookmarks."""
        if self.request.user.is_authenticated:
            return {"user_id": self.request.user.pk}
        return {"session_id": self._ensure_session_key()}


class BookmarkPageMixin(BookmarkAuthMixin):
    """Update the bookmark if the bookmark param was passed."""

    def update_bookmark(self) -> None:
        """Update the bookmark if the bookmark param was passed."""
        if TYPE_CHECKING:
            self.kwargs: dict  # pyright: ignore[reportUninitializedInstanceVariable]
        auth_filter = self.get_bookmark_auth_filter()
        comic_pks = (comic_pk,) if (comic_pk := self.kwargs.get("pk")) else ()
        page = self.kwargs.get("page")
        updates = {"page": page}

        task = BookmarkUpdateTask(auth_filter, comic_pks, updates)
        LIBRARIAN_QUEUE.put(task)


class BookmarkPageView(BookmarkPageMixin, AuthAPIView):
    """Display a comic page from the archive itself."""

    def put(self, *_args, **_kwargs) -> Response:
        """Update the bookmark."""
        self.update_bookmark()
        return Response()

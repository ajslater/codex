"""Views for reading comic books."""

from abc import ABC
from typing import TYPE_CHECKING

from django.db.models import Exists, OuterRef
from django.db.models.query_utils import Q
from rest_framework.response import Response

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Bookmark
from codex.views.auth import AuthAPIView, AuthMixin, GroupACLMixin

if TYPE_CHECKING:
    from rest_framework.request import Request

    from codex.models import BrowserCollectionModel


class BookmarkFilterMixin(GroupACLMixin, ABC):
    """Bookmark filter methods."""

    def init_bookmark_filter(self) -> None:
        """Initialize the bm_annotation_data."""
        if TYPE_CHECKING:
            self.request: Request
        self._bm_rels: dict[BrowserCollectionModel, str] = {}
        self._bm_filters: dict[BrowserCollectionModel, Q] = {}

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
            session_key = self.request.session.session_key
            if not session_key:
                # An anonymous visitor with no established session owns no
                # bookmarks. Returning the raw ``session_id IS NULL`` filter
                # here would match *every* authenticated user's bookmarks
                # (their ``session_id`` is NULL), leaking read state and
                # progress across users. Match nothing instead; a session key
                # is created only when the visitor actually writes a bookmark.
                return Q(pk__in=())
            key = f"{bm_rel}__session"
            value = session_key
        my_bookmarks_kwargs = {key: value}
        return Q(**my_bookmarks_kwargs)

    def get_my_finished_bookmark_exists(self, model) -> Exists:
        """
        Build a correlated probe for my finished bookmark on the comic row.

        Correlates on the queryset's comic pk (``rel_prefix + pk``), so on
        collection querysets it binds to the same joined comic row as the
        other comic-relation filters in the combined ``.filter()`` call —
        preserving the "one comic satisfies all conditions" semantics.
        """
        outer_pk = self.get_rel_prefix(model) + "pk"
        if self.request.user and self.request.user.is_authenticated:
            my = Q(user=self.request.user)
        else:
            my = Q(session=self.request.session.session_key)
        return Exists(
            Bookmark.objects.filter(my, comic=OuterRef(outer_pk), finished=True)
        )


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

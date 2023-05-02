"""Views for reading comic books."""
from django.db.models import F
from django.urls import reverse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import Bookmark, Comic
from codex.serializers.reader import ReaderInfoSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.views.bookmark import BookmarkBaseView
from codex.views.session import BrowserSessionViewBase

LOG = get_logger(__name__)
PAGE_TTL = 60 * 60 * 24


class ReaderView(BookmarkBaseView):
    """Get info for displaying comic pages."""

    serializer_class = ReaderInfoSerializer

    SETTINGS_ATTRS = ("fit_to", "two_pages", "read_in_reverse", "vertical")
    _SELECT_RELATED_FIELDS = ("series", "volume")
    _COMIC_FIELDS = (
        "file_type",
        "issue",
        "issue_suffix",
        "max_page",
        "series",
        "volume",
        "read_ltr",
    )

    def _append_with_settings(self, books, book, bookmark_filter):
        """Get bookmarks and filename and append to book list."""
        book.settings = (
            Bookmark.objects.filter(**bookmark_filter, comic=book)
            .only(*self.SETTINGS_ATTRS)
            .first()
        )
        book.filename = book.filename()
        books.append(book)

    def _get_comic_query_params(self, pk):
        """Get the reader naviation group filter."""
        session = self.request.session.get(BrowserSessionViewBase.SESSION_KEY, {})
        top_group = session.get("top_group")

        if top_group == "f":
            rel = "parent_folder__comic"
            ordering = ("path", "pk")
            select_related_fields = (*self._SELECT_RELATED_FIELDS, "parent_folder")
            fields = (*self._COMIC_FIELDS, "parent_folder")
        else:
            rel = "series__comic"
            ordering = Comic.ORDERING
            select_related_fields = self._SELECT_RELATED_FIELDS
            fields = self._COMIC_FIELDS

        return (
            {rel: pk},
            select_related_fields,
            fields,
            ordering,
        )

    def _get_group_comics(self):
        """Get comics for the series or folder."""
        pk = self.kwargs.get("pk")
        group_acl_filter = self.get_group_acl_filter(True)
        (
            group_nav_filter,
            select_related_fields,
            fields,
            ordering,
        ) = self._get_comic_query_params(pk)

        return (
            Comic.objects.filter(group_acl_filter)
            .filter(**group_nav_filter)
            .select_related(*select_related_fields)
            .only(*fields)
            .annotate(
                series_name=F("series__name"),
                volume_name=F("volume__name"),
                issue_count=F("volume__issue_count"),
            )
            .order_by(*ordering)
        )

    def _raise_not_found(self):
        """Raise not found exception."""
        pk = self.kwargs.get("pk")
        detail = {
            "route": reverse("app:start"),
            "reason": f"comic {pk} not found",
            "serializer": ReaderRedirectSerializer,
        }
        raise NotFound(detail=detail)

    def get_object(self):
        """Get the previous and next comics in a series.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.
        """
        comics = self._get_group_comics()
        bookmark_filter = self.get_bookmark_filter()

        # Select the -1, +1 window around the current issue
        # Yields 1 to 3 books
        books = []
        prev_book = None
        pk = self.kwargs.get("pk")
        for index, book in enumerate(comics):
            book.series_index = index + 1  # type: ignore
            if books:
                # after match set next comic and break
                self._append_with_settings(books, book, bookmark_filter)
                break
            if book.pk == pk:
                # first match. set previous and current comic
                if prev_book:
                    self._append_with_settings(books, prev_book, bookmark_filter)
                self._append_with_settings(books, book, bookmark_filter)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book

        if not books:
            self._raise_not_found()

        return {"books": books, "series_count": comics.count()}

    def get(self, *args, **kwargs):
        """Get the book info."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

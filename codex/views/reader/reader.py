"""Views for reading comic books."""
from django.db.models import F, FilteredRelation, Q
from django.urls import reverse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.models import Comic
from codex.serializers.reader import ReaderInfoSerializer
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.bookmark import BookmarkBaseView


LOG = get_logger(__name__)
PAGE_TTL = 60 * 60 * 24


class ReaderView(BookmarkBaseView):
    """Get info for displaying comic pages."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    serializer_class = ReaderInfoSerializer

    SETTINGS_ATTRS = ("fit_to", "two_pages")

    @classmethod
    def _append_with_settings(cls, books, book):
        settings = {}
        for attr in cls.SETTINGS_ATTRS:
            settings[attr] = book[f"settings__{attr}"]
        book["settings"] = settings
        books.append(book)

    def get_object(self):
        """
        Get the previous and next comics in a series.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.
        """
        pk = self.kwargs.get("pk")
        group_acl_filter = self.get_group_acl_filter(True)
        bookmark_filter = self.get_bookmark_filter()
        # get comic relations lazily. Only going to use 2-3 of them.
        comics = (
            Comic.objects.filter(group_acl_filter)
            .filter(series__comic=pk)
            .annotate(
                series_name=F("series__name"),
                volume_name=F("volume__name"),
                issue_count=F("volume__issue_count"),
                settings=FilteredRelation("bookmark", condition=Q(**bookmark_filter)),
            )
            .order_by(*Comic.ORDERING)
            .values(
                "pk",
                "file_format",
                "issue",
                "issue_count",
                "issue_suffix",
                "max_page",
                "series_name",
                "settings__fit_to",
                "settings__two_pages",
                "volume_name",
            )
        )

        # Select the -1, +1 window around the current issue
        # Yields 1 to 3 books
        books = []
        prev_book = None
        for index, book in enumerate(comics):
            book["series_index"] = index + 1
            if books:
                # after match set next comic and break
                self._append_with_settings(books, book)
                break
            elif book["pk"] == pk:
                # first match. set previous and current comic
                if prev_book:
                    self._append_with_settings(books, prev_book)
                self._append_with_settings(books, book)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book

        if not comics:
            pk = self.kwargs.get("pk")
            detail = {
                "route": reverse("app:start"),
                "reason": f"comic {pk} not found",
                "serializer": ReaderRedirectSerializer,
            }
            raise NotFound(detail=detail)

        return {"books": books, "series_count": comics.count()}

    def get(self, request, *args, **kwargs):
        """Get the book info."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

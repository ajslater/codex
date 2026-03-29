"""Get Books methods."""

from django.db.models import F
from django.db.models.query import Q, QuerySet
from django.urls import reverse
from rest_framework.exceptions import NotFound

from codex.models import Comic
from codex.models.bookmark import Bookmark
from codex.models.settings import SettingsReader
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.views.bookmark import BookmarkAuthMixin
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.const import (
    FOLDER_GROUP,
    GROUP_RELATION,
    NONE_INTEGERFIELD,
    STORY_ARC_GROUP,
)
from codex.views.mixins import SharedAnnotationsMixin
from codex.views.reader.arcs import ReaderArcsView

_COMIC_FIELDS = (
    "file_type",
    "issue_number",
    "issue_suffix",
    "page_count",
    "series",
    "volume",
    "reading_direction",
    "updated_at",
)
_ISSUE_ORDERING = (
    "issue_number",
    "issue_suffix",
    "sort_name",
)


class ReaderBooksView(ReaderArcsView, SharedAnnotationsMixin, BookmarkAuthMixin):
    """Get Books methods."""

    def _get_reader_settings_auth_filter(self) -> dict:
        """Get the auth filter for SettingsReader queries."""
        auth_filter = self.get_bookmark_auth_filter()
        # Add client type for SettingsReader.
        return {**auth_filter, "client": "api"}

    def _append_with_settings(self, book):
        """Append per-comic reader settings and bookmark to book."""
        reader_auth = self._get_reader_settings_auth_filter()
        book.settings = SettingsReader.objects.filter(**reader_auth, comic=book).first()
        bookmark_auth = self.get_bookmark_auth_filter()
        book.bookmark = (
            Bookmark.objects.filter(**bookmark_auth, comic=book)
            .only("page", "finished")
            .first()
        )
        return book

    def _raise_not_found(self) -> None:
        """Raise not found exception."""
        pk = self.kwargs.get("pk")
        detail = {
            "route": reverse("app:start"),
            "reason": f"comic {pk} not found",
            "serializer": ReaderRedirectSerializer,
        }
        raise NotFound(detail=detail)

    def _get_comics_filter(self, rel):
        """Build the filter."""
        group_acl_filter = self.get_group_acl_filter(Comic, self.request.user)
        nav_filter = {f"{rel}__in": self._selected_arc_ids}
        query_filter = group_acl_filter & Q(**nav_filter)
        if browser_filters := self.get_from_settings("filters", browser=True):
            # no search at this time.
            query_filter &= ComicFieldFilterView.get_all_comic_field_filters(
                "", browser_filters
            )
        return query_filter

    def _get_comics_annotation_and_ordering(
        self, model, ordering
    ) -> tuple[dict, tuple]:
        """Get ordering for query."""
        sort_name_annotations = {}
        if self._selected_arc_group in "sv":
            parent_group = "i" if self._selected_arc_group == "s" else "s"
            show = self.get_from_settings("show", browser=True)
            sort_name_annotations = self.get_sort_name_annotations(
                model, parent_group, self._selected_arc_ids, show
            )
            if sort_name_annotations and model is Comic:
                ordering += (*sort_name_annotations.keys(),)
            ordering += _ISSUE_ORDERING
        return sort_name_annotations, tuple(ordering)

    def _get_comics_list(self) -> QuerySet:
        """Get the reader navigation group filter."""
        rel = GROUP_RELATION[self._selected_arc_group]
        fields = _COMIC_FIELDS
        arc_pk_rel = rel + "__pk"
        arc_index = NONE_INTEGERFIELD
        select_related = ()
        prefetch_related = ()
        ordering = ()

        if self._selected_arc_group == STORY_ARC_GROUP:
            arc_index = F("story_arc_numbers__number")
            prefetch_related = (*prefetch_related, rel)
            ordering = ("arc_index", "date", "pk")
        elif self._selected_arc_group == FOLDER_GROUP:
            fields = (*_COMIC_FIELDS, rel)
            select_related = (rel,)
            ordering = ("path", "pk")

        query_filter = self._get_comics_filter(rel)
        qs = Comic.objects.filter(query_filter)

        if prefetch_related:
            qs = qs.prefetch_related(*prefetch_related)
        if select_related:
            qs = qs.select_related(*select_related)
        qs = qs.only(*fields)
        qs = self.annotate_group_names(qs)
        qs = qs.annotate(
            volume_number_to=(F("volume__number_to")),
            issue_count=F("volume__issue_count"),
            arc_pk=F(arc_pk_rel),
            arc_index=arc_index,
            mtime=F("updated_at"),
            has_metadata=F("metadata_mtime"),
        )
        sort_names_alias, ordering = self._get_comics_annotation_and_ordering(
            qs.model, ordering
        )
        if sort_names_alias:
            qs = qs.alias(**sort_names_alias)
        return qs.order_by(*ordering)

    def get_book_collection(self) -> dict:
        """
        Get the -1, +1 window around the current issue.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.

        Yields 1 to 3 books
        """
        comics = self._get_comics_list()
        books = {}
        prev_book = None
        pk = self.kwargs.get("pk")
        for index, book in enumerate(comics):
            if books:
                # after match set next comic and break
                books["next"] = self._append_with_settings(book)
                break
            if book.pk == pk:
                # first match. set previous and current comic
                if prev_book:
                    books["prev"] = self._append_with_settings(prev_book)
                # create extra current book attrs:
                book.filename = book.get_filename()
                self._selected_arc_index = index + 1
                self._selected_arc_count = comics.count()
                books["current"] = self._append_with_settings(book)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book

        if not books.get("current"):
            self._raise_not_found()
        return books

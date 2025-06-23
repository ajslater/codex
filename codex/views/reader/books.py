"""Get Books methods."""

from comicbox.box import Comicbox
from django.db.models import F
from django.db.models.query import Q, QuerySet
from django.urls import reverse
from loguru import logger
from rest_framework.exceptions import NotFound

from codex.librarian.importer.tasks import LazyImportComicsTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models import Bookmark, Comic
from codex.serializers.redirect import ReaderRedirectSerializer
from codex.settings import COMICBOX_CONFIG
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

_SETTINGS_ATTRS = ("fit_to", "two_pages", "reading_direction")
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

    @staticmethod
    def _get_bookmark_filter(auth_filter, comic_filter=None):
        """Get the search kwargs for a user's authentication state."""
        # search kwargs are relative to the bookmark object.
        search_kwargs = {}
        search_kwargs.update(auth_filter)

        if comic_filter:
            for key, value in comic_filter.items():
                search_kwargs[f"comic__{key}"] = value

        return search_kwargs

    @staticmethod
    def _append_with_settings(book, bookmark_filter):
        """Append bookmark to book list."""
        book.settings = (
            Bookmark.objects.filter(**bookmark_filter, comic=book)
            .only(*_SETTINGS_ATTRS)
            .first()
        )
        return book

    @staticmethod
    def _lazy_metadata(books):
        """Get reader metadata from comicbox if it's not in the db."""
        current = books.get("current")

        import_pks = set()
        if current and not (current.page_count and current.file_type):
            with Comicbox(current.path) as cb:
                current.file_type = cb.get_file_type()
                current.page_count = cb.get_page_count()
            import_pks.add(current.pk)

        prev_book = books.get("prev")
        if prev_book and not prev_book.page_count:
            with Comicbox(prev_book.path) as cb:
                prev_book.page_count = cb.get_page_count()
            import_pks.add(prev_book.pk)

        next_book = books.get("next")
        if next_book and not next_book.page_count:
            with Comicbox(next_book.path, config=COMICBOX_CONFIG, logger=logger) as cb:
                next_book.page_count = cb.get_page_count()
            import_pks.add(next_book.pk)

        if import_pks:
            task = LazyImportComicsTask(frozenset(import_pks))
            LIBRARIAN_QUEUE.put(task)

    def _raise_not_found(self):
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
        if browser_filters := self.get_from_session(
            "filters", session_key=self.BROWSER_SESSION_KEY
        ):
            # no search at this time.
            query_filter &= ComicFieldFilterView.get_all_comic_field_filters(
                "", browser_filters
            )
        return query_filter

    def _get_comics_annotation_and_ordering(self, model, ordering):
        """Get ordering for query."""
        sort_name_annotations = {}
        if self._selected_arc_group in "sv":
            parent_group = "i" if self._selected_arc_group == "s" else "s"
            show = self.get_from_session("show", session_key=self.BROWSER_SESSION_KEY)
            sort_name_annotations = self.get_sort_name_annotations(
                model, parent_group, self._selected_arc_ids, show
            )
            if sort_name_annotations and model is Comic:
                ordering += (*sort_name_annotations.keys(),)
            ordering += _ISSUE_ORDERING
        return sort_name_annotations, tuple(ordering)

    def _get_comics_list(self) -> QuerySet:
        """Get the reader naviation group filter."""
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
            issue_count=F("volume__issue_count"),
            arc_pk=F(arc_pk_rel),
            arc_index=arc_index,
            mtime=F("updated_at"),
        )
        sort_names_alias, ordering = self._get_comics_annotation_and_ordering(
            qs.model, ordering
        )
        if sort_names_alias:
            qs = qs.alias(**sort_names_alias)
        return qs.order_by(*ordering)

    def get_book_collection(self):
        """
        Get the -1, +1 window around the current issue.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.

        Yields 1 to 3 books
        """
        comics = self._get_comics_list()
        auth_filter = self.get_bookmark_auth_filter()
        bookmark_filter = self._get_bookmark_filter(auth_filter)
        books = {}
        prev_book = None
        pk = self.kwargs.get("pk")
        for index, book in enumerate(comics):
            if books:
                # after match set next comic and break
                books["next"] = self._append_with_settings(book, bookmark_filter)
                break
            if book.pk == pk:
                # first match. set previous and current comic
                if prev_book:
                    books["prev"] = self._append_with_settings(
                        prev_book, bookmark_filter
                    )
                # create extra current book attrs:
                book.filename = book.get_filename()
                self._selected_arc_index = index + 1
                self._selected_arc_count = comics.count()
                books["current"] = self._append_with_settings(book, bookmark_filter)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book

        if not books.get("current"):
            self._raise_not_found()
        self._lazy_metadata(books)
        return books

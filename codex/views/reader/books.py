"""Get Books methods."""

from typing import TYPE_CHECKING

from django.db.models import F
from django.db.models.query import Q

from codex.models import Bookmark, Comic
from codex.views.bookmark import BookmarkBaseView
from codex.views.browser.filters.field import ComicFieldFilterView
from codex.views.const import (
    FOLDER_GROUP,
    GROUP_MODEL_MAP,
    GROUP_RELATION,
    NONE_INTEGERFIELD,
    STORY_ARC_GROUP,
)
from codex.views.mixins import BookmarkSearchMixin, SharedAnnotationsMixin
from codex.views.reader.params import ReaderParamsView

if TYPE_CHECKING:
    from collections.abc import Mapping

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


class ReaderBooksView(
    BookmarkBaseView, ReaderParamsView, SharedAnnotationsMixin, BookmarkSearchMixin
):
    """Get Books methods."""

    def _get_reader_arc_pks(
        self, arc, arc_pk_select_related, prefetch_related, arc_pk_rel, arc_group
    ):
        """Get the nav filter."""
        if arc_pks := arc.get("pks", ()):
            return arc_pks

        comic_pk = self.kwargs["pk"]
        try:
            arc_pk_qs = Comic.objects.filter(pk=comic_pk)
            arc_pk_qs = arc_pk_qs.select_related(*arc_pk_select_related)
            arc_pk_qs = arc_pk_qs.prefetch_related(*prefetch_related)
            arc_pk_qs = arc_pk_qs.values_list(arc_pk_rel, flat=True)
            arc_pk = arc_pk_qs.first()
        except IndexError:
            arc_pk = 0

        _, multi_arc_pks = self.get_group_pks_from_breadcrumbs([arc_group])
        if not arc_pk or arc_pk in multi_arc_pks:
            arc_pks = multi_arc_pks

        if not arc_pks:
            arc_pks = (arc_pk,)

        return arc_pks

    def _get_comics_filter(self, rel, arc, arc_pks):
        """Build the filter."""
        group_acl_filter = self.get_group_acl_filter(Comic, self.request.user)
        nav_filter = {f"{rel}__in": arc_pks}
        query_filter = group_acl_filter & Q(**nav_filter)
        if browser_filters := arc.get("filters"):
            # no search at this time.
            query_filter &= ComicFieldFilterView.get_all_comic_field_filters(
                "", browser_filters
            )
        return query_filter

    def _get_comics_annotation_and_ordering(self, model, arc_group, arc_pks, ordering):
        """Get ordering for query."""
        sort_name_annotations = {}
        if arc_group in ("v", "s"):
            show = self.params["show"]
            model_group = "i" if arc_group == "s" else "s"
            sort_name_annotations = self.get_sort_name_annotations(
                model, model_group, arc_pks, show
            )
            if sort_name_annotations and model is Comic:
                ordering += (*sort_name_annotations.keys(),)
            ordering += (
                "issue_number",
                "issue_suffix",
                "sort_name",
            )
        return sort_name_annotations, tuple(ordering)

    def _get_comics_list(self):
        """Get the reader naviation group filter."""
        arc: Mapping = self.params.get("arc", {})  # type: ignore

        arc_group = arc.get("group", "")
        if not GROUP_MODEL_MAP.get(arc_group):
            arc_group = "s"

        rel = GROUP_RELATION[arc_group]
        fields = _COMIC_FIELDS
        arc_pk_rel = rel + "__pk"
        arc_index = NONE_INTEGERFIELD
        arc_pk_select_related = (rel,)
        select_related = ()
        prefetch_related = ()
        ordering = ()

        if arc_group == STORY_ARC_GROUP:
            arc_index = F("story_arc_numbers__number")
            arc_pk_select_related = ()
            prefetch_related = (*prefetch_related, rel)
            ordering = ("arc_index", "date", "pk")
        elif arc_group == FOLDER_GROUP:
            fields = (*_COMIC_FIELDS, rel)
            select_related = (rel,)
            ordering = ("path", "pk")

        arc_pks = self._get_reader_arc_pks(
            arc, arc_pk_select_related, prefetch_related, arc_pk_rel, arc_group
        )

        query_filter = self._get_comics_filter(rel, arc, arc_pks)
        qs = Comic.objects.filter(query_filter)

        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch_related:
            qs = qs.prefetch_related(*prefetch_related)
        qs = qs.only(*fields)
        qs = self.annotate_group_names(qs)
        qs = qs.annotate(
            issue_count=F("volume__issue_count"),
            arc_pk=F(arc_pk_rel),
            arc_index=arc_index,
            mtime=F("updated_at"),
        )
        sort_names_alias, ordering = self._get_comics_annotation_and_ordering(
            qs.model, arc_group, arc_pks, ordering
        )
        if sort_names_alias:
            qs = qs.alias(**sort_names_alias)
        qs = qs.order_by(*ordering)
        return qs, arc_group

    def _append_with_settings(self, book, bookmark_filter):
        """Append bookmark to book list."""
        book.settings = (
            Bookmark.objects.filter(**bookmark_filter, comic=book)
            .only(*_SETTINGS_ATTRS)
            .first()
        )
        return book

    def get_book_collection(self):
        """Get the -1, +1 window around the current issue.

        Uses iteration in python. There are some complicated ways of
        doing this with __gt[0] & __lt[0] in the db, but I think they
        might be even more expensive.

        Yields 1 to 3 books
        """
        comics, arc_group = self._get_comics_list()
        auth_filter = self.get_bookmark_auth_filter()
        bookmark_filter = self.get_bookmark_search_kwargs(auth_filter)
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
                if book.arc_index is None:
                    book.arc_index = index + 1
                book.filename = book.get_filename()
                book.arc_group = arc_group
                book.arc_count = comics.count()
                books["current"] = self._append_with_settings(book, bookmark_filter)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book
        return books

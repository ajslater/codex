"""Get Books methods."""

from typing import TYPE_CHECKING

from django.db.models import F

from codex.models import Bookmark, Comic
from codex.views.bookmark import BookmarkBaseView
from codex.views.const import FOLDER_GROUP, NONE_INTEGERFIELD
from codex.views.mixins import SharedAnnotationsMixin
from codex.views.reader.init import ReaderInitView

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


class ReaderBooksView(BookmarkBaseView, ReaderInitView, SharedAnnotationsMixin):
    """Get Books methods."""

    def _get_reader_arc_pks(  # noqa: PLR0913
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

    def _get_comics_list(self):
        """Get the reader naviation group filter."""
        select_related = ("series", "volume")
        prefetch_related = ()

        arc: Mapping = self.params.get("arc", {})  # type: ignore

        arc_group = arc.get("group", "s")
        if arc_group == "a":
            # for story arcs
            rel = "story_arc_numbers__story_arc"
            fields = _COMIC_FIELDS
            arc_pk_rel = "story_arc_numbers__story_arc__pk"
            prefetch_related = (*prefetch_related, "story_arc_numbers__story_arc")
            arc_index = F("story_arc_numbers__number")
            ordering = ("arc_index", "date", "pk")
            arc_pk_select_related = ()
        elif arc_group == FOLDER_GROUP:
            # folder mode
            rel = "parent_folder"
            fields = (*_COMIC_FIELDS, "parent_folder")
            arc_pk_rel = "parent_folder__pk"
            arc_index = NONE_INTEGERFIELD
            ordering = ("path", "pk")
            arc_pk_select_related = ("parent_folder",)
        elif arc_group == "v":
            # volume
            rel = "volume"
            fields = _COMIC_FIELDS
            arc_pk_rel = "volume__pk"
            arc_index = NONE_INTEGERFIELD
            ordering = ()
            arc_pk_select_related = ("volume",)
        else:
            # series
            rel = "series"
            fields = _COMIC_FIELDS
            arc_pk_rel = "series__pk"
            arc_index = NONE_INTEGERFIELD
            ordering = ()
            arc_pk_select_related = ("series",)

        arc_pks = self._get_reader_arc_pks(
            arc, arc_pk_select_related, prefetch_related, arc_pk_rel, arc_group
        )
        nav_filter = {f"{rel}__in": arc_pks}
        group_acl_filter = self.get_group_acl_filter(Comic)

        qs = (
            Comic.objects.filter(group_acl_filter)
            .filter(**nav_filter)
            .select_related(*select_related)
            .prefetch_related(*prefetch_related)
            .only(*fields)
            .annotate(
                issue_count=F("volume__issue_count"),
            )
            .annotate(
                arc_pk=F(arc_pk_rel),
                arc_index=arc_index,
            )
            .annotate(mtime=F("updated_at"))
        )
        qs = self.annotate_group_names(qs, Comic)
        if arc_group in ("v", "s"):
            show = self.params["show"]
            model_group = "i" if arc_group == "s" else "s"
            qs, comic_sort_names = self.alias_sort_names(
                qs, Comic, pks=arc_pks, model_group=model_group, show=show
            )
            ordering = (
                *comic_sort_names,
                "issue_number",
                "issue_suffix",
                "sort_name",
            )
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
        bookmark_filter = self.get_bookmark_search_kwargs()
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

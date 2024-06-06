"""Get Books methods."""

from copy import deepcopy
from typing import TYPE_CHECKING

from django.db.models import F, IntegerField, Value

from codex.models import Bookmark, Comic
from codex.views.bookmark import BookmarkBaseView
from codex.views.const import FOLDER_GROUP
from codex.views.mixins import SharedAnnotationsMixin
from codex.views.session import SessionView

if TYPE_CHECKING:
    from collections.abc import Mapping

_MIN_CRUMB_WALKBACK_LEN = 3
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


class ReaderBooksView(BookmarkBaseView, SessionView, SharedAnnotationsMixin):
    """Get Books methods."""

    def get_series_pks_from_breadcrumbs(self):
        """Get Multi-Group pks from the breadcrumbs."""
        if self.series_pks:
            return self.series_pks
        breadcrumbs = self.get_from_session(
            "breadcrumbs", session_key=self.BROWSER_SESSION_KEY
        )
        if breadcrumbs:
            crumb = breadcrumbs[-1]
            crumb_group = crumb.get("group")
            if crumb_group == "v" and len(breadcrumbs) >= _MIN_CRUMB_WALKBACK_LEN:
                crumb = breadcrumbs[-2]
                crumb_group = crumb.get("group")
            if crumb_group == "s":
                self.series_pks = crumb.get("pks", ())

        return self.series_pks

    def _get_reader_arc_pks(
        self, arc, arc_pk_select_related, prefetch_related, arc_pk_rel
    ):
        """Get the nav filter."""
        arc_pks = arc.get("pks", ())
        if not arc_pks:
            comic_pk = self.kwargs["pk"]
            try:
                arc_pk_qs = Comic.objects.filter(pk=comic_pk)
                arc_pk_qs = arc_pk_qs.select_related(*arc_pk_select_related)
                arc_pk_qs = arc_pk_qs.prefetch_related(*prefetch_related)
                arc_pk = arc_pk_qs.values_list(arc_pk_rel, flat=True)[0]
            except IndexError:
                arc_pk = 0

            if arc_pk_rel == "series__pk":
                multi_arc_pks = self.get_series_pks_from_breadcrumbs()
                if not arc_pk or arc_pk in multi_arc_pks:
                    arc_pks = multi_arc_pks
            if not arc_pks:
                arc_pks = (arc_pk,)

        return arc_pks

    def _get_comics_list(self):
        """Get the reader naviation group filter."""
        select_related = ("series",)
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
            ordering = ("arc_index", "date")
            arc_pk_select_related = ()
        elif arc_group == FOLDER_GROUP:
            # folder mode
            rel = "parent_folder"
            fields = (*_COMIC_FIELDS, "parent_folder")
            arc_pk_rel = "parent_folder__pk"
            select_related = (*select_related, "parent_folder")
            arc_index = Value(None, IntegerField())
            ordering = ("path", "pk")
            arc_pk_select_related = ("parent_folder",)
        else:
            # browser mode.
            rel = "series"
            fields = _COMIC_FIELDS
            arc_pk_rel = "series__pk"
            arc_index = Value(None, IntegerField())
            ordering = ()
            arc_pk_select_related = ("series",)

        arc_pks = self._get_reader_arc_pks(
            arc,
            arc_pk_select_related,
            prefetch_related,
            arc_pk_rel,
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
        if arc_group == "s":
            show = deepcopy(
                self.get_from_session("show", session_key=self.BROWSER_SESSION_KEY)
            )
            show.pop("p", None)
            show.pop("i", None)
            qs, comic_sort_names = self.alias_sort_names(
                qs, Comic, pks=arc_pks, model_group="i", show=show
            )
            ordering = (
                *comic_sort_names,
                "issue_number",
                "issue_suffix",
                "sort_name",
            )
        return qs.order_by(*ordering), arc_group

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
        bookmark_filter = self.get_bookmark_filter()
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
                if book.arc_index is None:  # type: ignore
                    book.arc_index = index + 1  # type: ignore
                book.filename = book.get_filename()  # type: ignore
                book.arc_group = arc_group
                book.arc_count = comics.count()
                books["current"] = self._append_with_settings(book, bookmark_filter)
            else:
                # Haven't matched yet, so set the previous comic
                prev_book = book
        return books

    #####

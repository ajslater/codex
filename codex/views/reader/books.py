"""Get Books methods."""

from collections.abc import Callable

from django.db.models import BooleanField, ExpressionWrapper, F
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

    def _batch_settings_and_bookmarks(
        self, book_pks
    ) -> tuple[dict[int, SettingsReader], dict[int, Bookmark]]:
        """
        Per-pk SettingsReader + Bookmark lookups in two queries.

        Replaces the prior per-book ``filter().first()`` round-trips
        (2 queries times up to 3 books) with two ``filter(comic_id__in=...)``
        calls partitioned by comic_id (sub-plan 01 #3 / Tier 2 #4).
        """
        if not book_pks:
            return {}, {}
        reader_auth = self._get_reader_settings_auth_filter()
        settings_qs = SettingsReader.objects.filter(
            **reader_auth, comic_id__in=book_pks
        )
        settings_by_pk: dict[int, SettingsReader] = {
            s.comic_id: s  # pyright: ignore[reportAttributeAccessIssue]
            for s in settings_qs
        }
        bookmark_auth = self.get_bookmark_auth_filter()
        bookmark_qs = Bookmark.objects.filter(
            **bookmark_auth, comic_id__in=book_pks
        ).only("page", "finished", "comic_id")
        bookmarks_by_pk: dict[int, Bookmark] = {
            b.comic_id: b  # pyright: ignore[reportAttributeAccessIssue]
            for b in bookmark_qs
        }
        return settings_by_pk, bookmarks_by_pk

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
        acl_filter = self.get_acl_filter(Comic, self.request.user)
        nav_filter = {f"{rel}__in": self._selected_arc_ids}
        query_filter = acl_filter & Q(**nav_filter)
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
        # ``has_metadata`` is read as a ``BooleanField`` on the reader
        # serializer; selecting the IS-NOT-NULL predicate skips dragging a
        # full ``DateTimeField`` value through the result row.
        qs = qs.annotate(
            volume_number_to=(F("volume__number_to")),
            issue_count=F("volume__issue_count"),
            arc_pk=F(arc_pk_rel),
            arc_index=arc_index,
            mtime=F("updated_at"),
            has_metadata=ExpressionWrapper(
                Q(metadata_mtime__isnull=False), output_field=BooleanField()
            ),
        )
        sort_names_alias, ordering = self._get_comics_annotation_and_ordering(
            qs.model, ordering
        )
        if sort_names_alias:
            qs = qs.alias(**sort_names_alias)
        return qs.order_by(*ordering)

    @staticmethod
    def _get_book_collection_books(
        pk: int,
        prev_pk: int | None,
        next_pk: int | None,
        rows_by_pk: dict,
        _attach: Callable,
    ) -> dict:
        books: dict = {}
        if prev_pk is not None and prev_pk in rows_by_pk:
            books["prev"] = _attach(rows_by_pk[prev_pk])
        current = rows_by_pk[pk]
        current.filename = current.get_filename()
        books["current"] = _attach(current)
        if next_pk is not None and next_pk in rows_by_pk:
            books["next"] = _attach(rows_by_pk[next_pk])
        return books

    def get_book_collection(self) -> dict:
        """
        Get the -1, +1 window around the current issue.

        Yields 1-3 books (no prev for the first issue, no next for the
        last). Cost is constant w.r.t. arc size: one ``values_list("pk")``
        materialization (cheap — int columns only), one full
        ``filter(pk__in=window_pks)`` re-fetch for the 1-3 rows we
        actually want, and two batched lookups for SettingsReader /
        Bookmark (sub-plan 01 #1, #3).

        The prior implementation iterated the entire ordered queryset
        in Python to find prev/curr/next, materializing every row's
        full annotation pyramid even for a 100-issue series.
        """
        pk = self.kwargs.get("pk")
        comics = self._get_comics_list()

        # Materialize only pk integers in arc order. The annotation
        # pyramid (sort_name aliases, arc_index, has_metadata, …) still
        # contributes to the ORDER BY but isn't selected, so the row
        # data transfer is just N ints rather than N fully-annotated
        # Comic instances.
        pks = list(comics.values_list("pk", flat=True))
        try:
            current_idx = pks.index(pk)
        except ValueError:
            self._raise_not_found()
            return {}  # _raise_not_found raises; appease the type checker

        arc_count = len(pks)
        prev_pk = pks[current_idx - 1] if current_idx > 0 else None
        next_pk = pks[current_idx + 1] if current_idx + 1 < arc_count else None
        window_pks: list[int] = [p for p in (prev_pk, pk, next_pk) if p is not None]

        # Re-fetch the 1-3 actual rows with the full annotation pyramid.
        rows_by_pk = {row.pk: row for row in comics.filter(pk__in=window_pks)}
        settings_by_pk, bookmarks_by_pk = self._batch_settings_and_bookmarks(window_pks)

        def _attach(book):
            book.settings = settings_by_pk.get(book.pk)
            book.bookmark = bookmarks_by_pk.get(book.pk)
            return book

        books = self._get_book_collection_books(
            pk, prev_pk, next_pk, rows_by_pk, _attach
        )

        self._selected_arc_index = current_idx + 1
        self._selected_arc_count = arc_count
        return books

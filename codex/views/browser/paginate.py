"""Browser pagination."""

from django.core.paginator import Paginator
from django.db.models.query import QuerySet

from codex.settings.db import get_browser_max_obj_per_page
from codex.views.browser.page_in_bounds import BrowserPageInBoundsView
from codex.views.const import FOLDER_COLLECTION

_ORPHANS = 5


class BrowserPaginateView(BrowserPageInBoundsView):
    """Paginate Collections and Books."""

    def page_orphans(self, per_page: int) -> int:
        """Return how many leftover rows the last page takes in."""
        orphans = (
            0
            if self.model_collection == FOLDER_COLLECTION or self.params.get("search")
            else _ORPHANS
        )
        # Django 7.0 raises ValueError when orphans >= per_page; keep it below.
        # A small admin-configured page size would otherwise trip this.
        return min(orphans, per_page - 1)

    def get_browser_paginator(self, count: int) -> Paginator:
        """
        Paginate the collections and then the books as one list of rows.

        A ``range`` stands in for the rows, so the page count and each page's
        slice come from the same arithmetic, orphans included, without a query.
        An empty listing has no pages.
        """
        per_page = get_browser_max_obj_per_page()
        return Paginator(
            range(count),
            per_page,
            orphans=self.page_orphans(per_page),
            allow_empty_first_page=False,
        )

    @staticmethod
    def _slice_section(
        qs: QuerySet, start: int, stop: int, count: int
    ) -> tuple[QuerySet, int]:
        """Slice a section's share of the page's rows."""
        start, stop = max(start, 0), min(stop, count)
        if start >= stop:
            return qs.model.objects.none(), 0
        return qs[start:stop], stop - start

    def paginate(
        self,
        paginator: Paginator,
        collection_qs: QuerySet,
        book_qs: QuerySet,
        collection_count: int,
        book_count: int,
    ) -> tuple[QuerySet, QuerySet, int, int]:
        """Paginate the queryset into a collection and book object lists."""
        if self.TARGET == "opds2":
            self._opds_number_of_books = book_count
            self._opds_number_of_collections = collection_count

        if paginator.num_pages:
            page = paginator.page(self.kwargs.get("page", 1))
            start, stop = page.start_index() - 1, page.end_index()
        else:
            start = stop = 0

        page_collection_qs, page_collection_count = self._slice_section(
            collection_qs, start, stop, collection_count
        )
        # Books follow the collections in the rows.
        page_book_qs, page_book_count = self._slice_section(
            book_qs, start - collection_count, stop - collection_count, book_count
        )

        return page_collection_qs, page_book_qs, page_collection_count, page_book_count

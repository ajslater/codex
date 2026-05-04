"""Browser pagination."""

from math import ceil

from django.core.paginator import EmptyPage, Paginator
from django.db.models.query import QuerySet
from loguru import logger

from codex.settings import BROWSER_MAX_OBJ_PER_PAGE
from codex.views.browser.page_in_bounds import BrowserPageInBoundsView


class BrowserPaginateView(BrowserPageInBoundsView):
    """Paginate Groups and Books."""

    def _paginate_section(
        self, qs: QuerySet, page: int, total_count: int
    ) -> tuple[QuerySet, int]:
        """
        Paginate a group or Comic section.

        ``total_count`` is the pre-computed section total (already run by
        the caller via one grouped COUNT). It's stuffed into
        ``Paginator._count`` so Paginator skips its own COUNT query, and
        used to derive the page row count arithmetically instead of
        issuing another COUNT on the sliced queryset.
        """
        if not total_count:
            return qs.model.objects.none(), 0
        orphans = 0 if self.model_group == "f" or self.params.get("search") else 5
        paginator = Paginator(qs, BROWSER_MAX_OBJ_PER_PAGE, orphans=orphans)
        # Shadow the @cached_property with the pre-computed total so
        # Paginator.num_pages doesn't issue its own COUNT query.
        paginator.count = total_count  # pyright: ignore[reportAttributeAccessIssue], #ty: ignore[invalid-assignment]
        try:
            paginator_page = paginator.page(page)
            qs = paginator_page.object_list
            count = paginator_page.end_index() - paginator_page.start_index() + 1
        except EmptyPage:
            if self.model_group != "f":
                model_name = qs.model.__name__ if qs.model else "UnknownGroup"
                logger.warning(f"No {model_name}s on page {page}")
            qs = qs.model.objects.none()
            count = 0

        return qs, count

    def _paginate_groups(
        self, group_qs: QuerySet, group_count: int
    ) -> tuple[QuerySet, int]:
        """Paginate the group object list before books."""
        page = self.kwargs.get("page", 1)
        return self._paginate_section(group_qs, page, group_count)

    def _paginate_books(
        self,
        book_qs: QuerySet,
        book_count: int,
        total_group_count: int,
        page_group_count: int,
    ) -> tuple[QuerySet, int]:
        """Paginate the book object list based on how many group/folders are showing."""
        group_remainder = total_group_count % BROWSER_MAX_OBJ_PER_PAGE
        num_books_on_mixed_page = BROWSER_MAX_OBJ_PER_PAGE - group_remainder
        if page_group_count:
            # There are books after the groups on the same page
            # Add remainder books without the paginator
            page_book_qs = book_qs[:num_books_on_mixed_page]
            page_book_count = min(num_books_on_mixed_page, book_count)
            return page_book_qs, page_book_count

        # There are books after the groups on a new page
        book_offset = 0 if not group_remainder else num_books_on_mixed_page
        page_book_qs = book_qs[book_offset:]

        # Which book page are we on after groups?
        page = self.kwargs.get("page", 1)
        num_group_and_mixed_pages = ceil(total_group_count / BROWSER_MAX_OBJ_PER_PAGE)
        book_only_page = page - num_group_and_mixed_pages

        remaining_book_count = max(0, book_count - book_offset)
        return self._paginate_section(
            page_book_qs, book_only_page, remaining_book_count
        )

    def paginate(
        self,
        group_qs: QuerySet,
        book_qs: QuerySet,
        group_count: int,
        book_count: int,
    ) -> tuple[QuerySet, QuerySet, int, int]:
        """Paginate the queryset into a group and book object lists."""
        if self.TARGET == "opds2":
            self._opds_number_of_books = book_count
            self._opds_number_of_groups = group_count

        page_group_qs, page_group_count = self._paginate_groups(group_qs, group_count)
        page_book_qs, page_book_count = self._paginate_books(
            book_qs, book_count, group_count, page_group_count
        )

        return page_group_qs, page_book_qs, page_group_count, page_book_count

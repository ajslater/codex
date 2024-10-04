"""Browser pagination."""

from math import ceil

from django.core.paginator import EmptyPage, Paginator

from codex.logger.logging import get_logger
from codex.views.browser.page_in_bounds import BrowserPageInBoundsView
from codex.views.const import MAX_OBJ_PER_PAGE

LOG = get_logger(__name__)


class BrowserPaginateView(BrowserPageInBoundsView):
    """Paginate Groups and Books."""

    def _paginate_section(self, qs, page):
        """Paginate a group or Comic section."""
        orphans = 0 if self.model_group == "f" or self.params.get("q") else 5
        paginator = Paginator(qs, MAX_OBJ_PER_PAGE, orphans=orphans)
        try:
            paginator_page = paginator.page(page)
            qs = paginator_page.object_list
        except EmptyPage:
            if self.model_group != "f":
                model_name = qs.model.__name__ if qs.model else "UnknownGroup"
                LOG.warning(f"No {model_name}s on page {page}")
            qs = qs.model.objects.none()

        return qs

    def _paginate_groups(self, group_qs):
        """Paginate the group object list before books."""
        page = self.kwargs.get("page", 1)
        return self._paginate_section(group_qs, page)

    def _paginate_books(self, book_qs, total_group_count, page_group_count):
        """Paginate the book object list based on how many group/folders are showing."""
        group_remainder = total_group_count % MAX_OBJ_PER_PAGE
        num_books_on_mixed_page = MAX_OBJ_PER_PAGE - group_remainder
        if page_group_count:
            # There are books after the groups on the same page
            # Add remainder books without the paginator
            page_book_qs = book_qs[:num_books_on_mixed_page]
        else:
            # There are books after the groups on a new page
            book_offset = 0 if not group_remainder else num_books_on_mixed_page
            page_book_qs = book_qs[book_offset:]

            # Which book page are we on after groups?
            page = self.kwargs.get("page", 1)
            num_group_and_mixed_pages = ceil(total_group_count / MAX_OBJ_PER_PAGE)
            book_only_page = page - num_group_and_mixed_pages

            page_book_qs = self._paginate_section(page_book_qs, book_only_page)
        return page_book_qs

    def paginate(self, group_qs, book_qs, group_count):
        """Paginate the queryset into a group and book object lists."""
        page_group_qs = self._paginate_groups(group_qs)
        page_group_count = page_group_qs.count()
        page_book_qs = self._paginate_books(book_qs, group_count, page_group_count)
        page_book_count = page_book_qs.count()

        return page_group_qs, page_book_qs, page_group_count, page_book_count

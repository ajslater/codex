"""Browser pagination."""

from math import ceil

from django.core.paginator import EmptyPage, Paginator

from codex.logger.logging import get_logger
from codex.models import (
    Comic,
    Folder,
)
from codex.views.browser.annotations import BrowserAnnotationsView
from codex.views.const import (
    MAX_OBJ_PER_PAGE,
)
from codex.views.util import Route

LOG = get_logger(__name__)


class BrowserPaginateView(BrowserAnnotationsView):
    """Browser pagination."""

    def _get_back_one_page_route(self, num_pages):
        """Get max page if oob or 1."""
        LOG.debug("Redirect back one page.")
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        page = self.kwargs.get("page", 1)
        new_page = num_pages if num_pages and page > num_pages else 1
        pks = pks if pks else "0"
        return {"group": group, "pks": pks, "page": new_page}

    def _get_up_breadcrumbs(self):
        """Walk up the breadcrumbs to get the next level up."""
        breadcrumbs = self.params.get("breadcrumbs", [])
        new_breadcrumbs = []
        level = False
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        page = self.kwargs.get("page", 1)
        current_route = Route(group=group, pks=pks, page=page)
        for crumb in reversed(breadcrumbs):
            if not level:
                crumb_route = Route(**crumb)
                level = current_route & crumb_route
                continue
            new_breadcrumbs = [crumb, *new_breadcrumbs]

        if not new_breadcrumbs:
            if group not in ("f", "a"):
                group = "r"
            top_route = {"group": group, "pks": (), "page": 1}
            new_breadcrumbs = [top_route]
        return new_breadcrumbs

    def _get_up_page_redirect(self):
        """Walk up the breadcrumbs."""
        try:
            up_breadcrumbs = self._get_up_breadcrumbs()
            route_mask = up_breadcrumbs[-1]
            settings_mask = {"breadcrumbs": up_breadcrumbs}
            LOG.debug("Redirect up a level.")
        except IndexError:
            group = self.kwargs.get("group")
            pks = "0"
            new_page = 1
            route_mask = {"group": group, "pks": pks, "page": new_page}
            settings_mask = {"breadcrumbs": [route_mask]}
            LOG.debug("Redirect to all at current group.")
        return route_mask, settings_mask

    def _check_page_in_bounds(self, total_count):
        """Redirect page out of bounds."""
        pks = self.kwargs.get("pks")
        page = self.kwargs.get("page", 1)
        num_pages = ceil(total_count / MAX_OBJ_PER_PAGE)
        if page == 1 or (page >= 1 and page <= num_pages):
            # Don't redirect if on the root page for the group.
            # Or page within valid range.
            return num_pages

        group = self.kwargs.get("group")
        reason = f"{group=} {pks=} {page=} does not exist."

        # Adjust route mask for redirect
        if num_pages and page > 1:
            route_mask = self._get_back_one_page_route(num_pages)
            settings_mask = None
        else:
            # This now only occurs when page < 1
            route_mask, settings_mask = self._get_up_page_redirect()

        return self.raise_redirect(
            reason, route_mask=route_mask, settings_mask=settings_mask
        )

    def _paginate_section(self, model, qs, page):
        """Paginate a group or Comic section."""
        orphans = 0 if self.model_group == "f" or self.params.get("q") else 5
        paginator = Paginator(qs, MAX_OBJ_PER_PAGE, orphans=orphans)
        try:
            qs = paginator.page(page).object_list
        except EmptyPage:
            if model != Folder:
                model_name = self.model.__name__ if self.model else "NO_MODEL"
                LOG.warning(f"No {model_name}s on page {page}")
            qs = model.objects.none()

        return qs

    def _paginate_groups(self, group_qs, total_group_count):
        """Paginate the group object list before books."""
        if total_group_count:
            page = self.kwargs.get("page", 1)
            page_group_qs = self._paginate_section(self.model, group_qs, page)
        else:
            page_group_qs = self.model.objects.none()  # type: ignore
        return page_group_qs

    def _paginate_books(self, book_qs, total_group_count, page_obj_count):
        """Paginate the book object list based on how many group/folders are showing."""
        if page_obj_count >= MAX_OBJ_PER_PAGE:
            # No books for this page
            page_book_qs = Comic.objects.none()
        else:
            group_remainder = total_group_count % MAX_OBJ_PER_PAGE
            if page_obj_count:
                # There are books after the groups on the same page
                # Manually add books without the paginator
                book_limit = MAX_OBJ_PER_PAGE - group_remainder
                page_book_qs = book_qs[:book_limit]
            else:
                # There are books after the groups on a new page
                if group_remainder:
                    book_offset = MAX_OBJ_PER_PAGE - group_remainder
                    page_book_qs = book_qs[book_offset:]
                else:
                    page_book_qs = book_qs

                num_group_and_mixed_pages = ceil(total_group_count / MAX_OBJ_PER_PAGE)
                book_only_page = self.kwargs.get("page", 1) - num_group_and_mixed_pages
                page_book_qs = self._paginate_section(
                    Comic, page_book_qs, book_only_page
                )
        return page_book_qs

    def paginate(self, group_qs, book_qs, group_count, book_count):
        """Paginate the queryset into a group and book object lists."""
        num_pages = self._check_page_in_bounds(group_count + book_count)
        page_group_qs = self._paginate_groups(group_qs, group_count)
        page_group_count = page_group_qs.count()
        page_book_qs = self._paginate_books(book_qs, group_count, page_group_count)
        page_book_count = page_book_qs.count()

        return page_group_qs, page_book_qs, num_pages, page_group_count, page_book_count

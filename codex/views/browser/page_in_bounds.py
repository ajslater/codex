"""Browser Page Bounds Checking."""

from codex.logger.logging import get_logger
from codex.views.browser.annotate.card import BrowserAnnotateCardView
from codex.views.util import Route

LOG = get_logger(__name__)


class BrowserPageInBoundsView(BrowserAnnotateCardView):
    """Browser Page Bounds Checking."""

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

    def _handle_page_out_of_bounds(self, num_pages):
        """Handle out of bounds redirect."""
        # Try to find a logical page to run to.
        group = self.kwargs.get("group")
        page = self.kwargs.get("page", 1)
        pks = self.kwargs.get("pks")
        reason = f"{group=} {pks=} {page=} does not exist."

        # Adjust route mask for redirect
        if num_pages and page > 1:
            route_mask = self._get_back_one_page_route(num_pages)
            settings_mask = None
        else:
            # This now only occurs when page < 1
            route_mask, settings_mask = self._get_up_page_redirect()

        self.raise_redirect(reason, route_mask=route_mask, settings_mask=settings_mask)

    def check_page_in_bounds(self, num_pages: int):
        """Redirect page out of bounds."""
        page = self.kwargs.get("page", 1)
        if page == 1 or (page >= 1 and page <= num_pages):
            # Don't redirect if on the root page for the group.
            # Or page within valid range.
            return

        self._handle_page_out_of_bounds(num_pages)

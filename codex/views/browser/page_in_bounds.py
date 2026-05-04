"""Browser Page Bounds Checking."""

from typing import Any

from loguru import logger

from codex.views.browser.annotate.cover import BrowserAnnotateCoverView


class BrowserPageInBoundsView(BrowserAnnotateCoverView):
    """Browser Page Bounds Checking."""

    def _get_back_one_page_route(self, num_pages) -> dict[str, Any]:
        """Get max page if oob or 1."""
        logger.debug("Redirect back one page.")
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        page = self.kwargs.get("page", 1)
        new_page = num_pages if num_pages and page > num_pages else 1
        pks = pks or (0,)
        return {"group": group, "pks": pks, "page": new_page}

    def _get_up_page_redirect(self) -> tuple[dict, None]:
        """Get a parent route to redirect to when page is out of bounds."""
        group = self.kwargs.get("group")
        if group not in ("f", "a"):
            group = "r"
        route_mask = {"group": group, "pks": (), "page": 1}
        logger.debug("Redirect up a level.")
        return route_mask, None

    def _handle_page_out_of_bounds(self, num_pages) -> None:
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

    def check_page_in_bounds(self, num_pages: int) -> None:
        """Redirect page out of bounds."""
        page = self.kwargs.get("page", 1)
        # ``page == 1`` is the root page and is always in bounds,
        # even when the group is empty (``num_pages == 0`` — the
        # state on a fresh install where the importer hasn't run
        # yet). Without that special case, an empty database
        # redirects ``r/0/1`` → ``_get_up_page_redirect`` →
        # ``r/0/1`` and loops. The earlier "simplification" to
        # ``1 <= page <= num_pages`` collapsed both clauses into
        # one but dropped this exact corner case.
        if page == 1 or 1 <= page <= num_pages:
            return

        self._handle_page_out_of_bounds(num_pages)

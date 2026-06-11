"""
Codex pagination classes.

Browser views use DRF's stock page-number pagination (the UI surfaces
an explicit page-N control). Admin lists use cursor pagination so the
frontend can stream large user / library / cover lists without paying
for the offset re-scan on every fetch.
"""

from rest_framework.pagination import CursorPagination


class CodexCursorPagination(CursorPagination):
    """
    Cursor pagination for admin lists.

    Ordering defaults to ``pk`` (every admin model has one and it's
    stably indexed); page size is large enough that typical
    installations land on one page.
    """

    ordering = "pk"
    page_size = 200
    page_size_query_param = "limit"
    max_page_size = 1000


class LibrarianStatusCursorPagination(CodexCursorPagination):
    """
    Cursor pagination for the librarian status endpoints.

    ``CursorPagination`` re-orders the queryset with its own ordering,
    silently discarding the view's ``order_by`` — the plain ``pk``
    default scrambled the sidebar progress feed into row-creation
    order (read next to search, query below create). The active poll
    must follow the importer's ``start_many`` registration stamps:
    ``preactive`` (padded registration order), then ``active`` for
    rows started without pre-registration (SQLite sorts their NULL
    preactive first — wanted, see CreateCoversStatus in
    importer/init.py), then ``pk``.

    Nullable cursor fields would misbehave if a cursor ever pointed
    past page one, but the active feed is ~20 rows against a 200-row
    page, so the cursor filter never engages. The Jobs tab history
    view keeps the ``pk`` default.
    """

    def get_ordering(self, request, queryset, view) -> tuple[str, ...]:
        """Registration-stamp order for the active poll; pk for history."""
        if getattr(view, "active_only", False):
            return ("preactive", "active", "pk")
        return super().get_ordering(request, queryset, view)

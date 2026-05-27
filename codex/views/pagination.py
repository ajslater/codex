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

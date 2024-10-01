"""Browser Filters."""

from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView

LOG = get_logger(__name__)


class BrowserFilterView(BrowserFilterBookmarkView):
    """Browser Filters."""

    TARGET = ""

    def force_inner_joins(self, qs):
        """Force INNER JOINS to filter empty groups."""
        demote_tables = {"codex_library"}
        if qs.model is not Comic:
            demote_tables.add("codex_comic")
        if self.fts_mode:
            # Forcing INNER JOINS required to make fts5 work
            demote_tables.add("codex_comicfts")
        return qs.demote_joins(demote_tables)

    def _get_query_filters( # noqa: PLR0913
        self,
        model,
        subquery=False,
        group=None,
        pks=None,
        page_mtime=False,
        bookmark_filter=True,
    ) -> Q:
        """Return all the filters except the group filter."""
        big_include_filter = Q()
        big_exclude_filter = Q()
        # TODO get exclude filter from acl filter
        #   when i refactor acl filter
        if not subquery:
            acl_include_filter = self.get_group_acl_filter(model)
            big_include_filter &= acl_include_filter
            big_include_filter &= self.get_group_filter(group, pks, page_mtime=page_mtime)
        big_include_filter &= self.get_comic_field_filter(model)
        if bookmark_filter:
            big_include_filter &= self.get_bookmark_filter(model)
        include_search_filter, exclude_search_filter, fts_q = self.get_search_filters(
            model
        )
        big_include_filter &= include_search_filter
        big_exclude_filter &= exclude_search_filter

        return big_include_filter & ~big_exclude_filter & fts_q

    def get_filtered_queryset( # noqa: PLR0913
        self,
        model,
        subquery=False,
        group=None,
        pks=None,
        page_mtime=False,
        bookmark_filter=True,
    ) -> QuerySet:
        """Get a filtered queryset for the model."""
        query_filters = self._get_query_filters(
            model,
            subquery=subquery,
            group=group,
            pks=pks,
            page_mtime=page_mtime,
            bookmark_filter=bookmark_filter,
        )
        return model.objects.filter(query_filters)

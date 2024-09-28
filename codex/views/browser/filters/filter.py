"""Browser Filters."""

from django.db.models.query_utils import Q

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView

LOG = get_logger(__name__)


class BrowserFilterView(BrowserFilterBookmarkView):
    """Browser Filters."""

    TARGET = ""

    def _filter_by_comic_exists(self, qs):
        """Filter by comics existing, allows INNER JOIN."""
        if qs.model is not Comic:
            rel = self.get_rel_prefix(qs.model)
            rel += "isnull"
            inner_join_filter = {rel: False}
            qs = qs.filter(**inner_join_filter)
        return qs

    def get_query_filters(  # noqa: PLR0913
        self,
        model,
        group,
        pks,
        bookmark_filter=True,
        page_mtime=False,
        group_filter=True,
        acl_filter=True,
        search_filter=True,
    ):
        """Return all the filters except the group filter."""
        include_filter = Q()
        exclude_filter = Q()
        if acl_filter:
            # TODO get exclude frilter from acl filter
            acl_include_filter = self.get_group_acl_filter(model)
            include_filter &= acl_include_filter
        if group_filter:
            include_filter &= self.get_group_filter(group, pks, page_mtime=page_mtime)
        include_filter &= self.get_comic_field_filter(model)
        if bookmark_filter:
            # not needed when used by outerrefl OuterRef is applied next
            include_filter &= self.get_bookmark_filter(model)
        if search_filter:
            include_search_filter, exclude_search_filter = self.get_search_filters(
                model
            )
            include_filter &= include_search_filter
            exclude_filter &= exclude_search_filter
        return include_filter & ~exclude_filter

    def get_filtered_queryset(  # noqa: PLR0913
        self,
        model,
        group=None,
        pks=None,
        bookmark_filter=True,
        page_mtime=False,
        group_filter=True,
        acl_filter=True,
    ):
        """Get a filtered queryset for the model."""
        object_filter = self.get_query_filters(
            model,
            group,
            pks,
            bookmark_filter,
            page_mtime=page_mtime,
            group_filter=group_filter,
            acl_filter=acl_filter,
        )
        qs = model.objects.filter(object_filter)
        qs = self._filter_by_comic_exists(qs)
        return qs.group_by("id")

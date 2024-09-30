"""Browser Filters."""

from types import MappingProxyType

from django.db.models.query_utils import Q

from codex.logger.logging import get_logger
from codex.models.comic import Comic
from codex.models.groups import BrowserGroupModel, Imprint, Publisher, Series, Volume
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView

_GROUP_BY: MappingProxyType[type[BrowserGroupModel], str] = MappingProxyType(
    {Publisher: "sort_name", Imprint: "sort_name", Series: "sort_name", Volume: "name"}
)
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

    def get_query_filters(  # noqa: PLR0913
        self,
        model,
        group,
        pks,
        bookmark_filter=True,
        page_mtime=False,
        group_filter=True,
        acl_filter=True,
    ):
        """Return all the filters except the group filter."""
        include_filters = []
        exclude_filters = []
        if acl_filter:
            # TODO get exclude filter from acl filter
            #   when i refactor acl filter
            acl_include_filter = self.get_group_acl_filter(model)
            include_filters.append(acl_include_filter)
        if group_filter:
            include_filters.append(
                self.get_group_filter(group, pks, page_mtime=page_mtime)
            )
        include_filters.append(self.get_comic_field_filter(model))
        if bookmark_filter:
            include_filters.append(self.get_bookmark_filter(model))
        include_search_filter, exclude_search_filter, fts_q = self.get_search_filters(
            model
        )
        include_filters.append(include_search_filter)
        exclude_filters.append(exclude_search_filter)
        # TODO clean up
        ic = Q()

        for include_filter in include_filters:
            ic &= include_filter
        ec = Q()
        for exclude_filter in exclude_filters:
            ec &= exclude_filter
        if ec:
            ic &= ~ec

        if fts_q:
            ic &= fts_q
        return ic

    def add_group_by(self, qs):
        """Get the group by for the model."""
        if group_by := _GROUP_BY.get(qs.model):  # type: ignore
            qs = qs.group_by(group_by)
        return qs

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
        qs = model.objects
        query_filters = self.get_query_filters(
            model,
            group,
            pks,
            bookmark_filter,
            page_mtime=page_mtime,
            group_filter=group_filter,
            acl_filter=acl_filter,
        )
        qs = qs.filter(query_filters)
        # TODO is group by neccessarcy here?
        return self.add_group_by(qs)

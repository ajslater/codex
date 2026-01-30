"""OPDS v2.0 Feed."""

import json
import urllib.parse
from collections.abc import Iterable, Mapping
from datetime import datetime
from types import MappingProxyType

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from typing_extensions import override

from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v2.feed import OPDS2FeedSerializer
from codex.settings import FALSY, MAX_OBJ_PER_PAGE
from codex.views.const import EPOCH_START
from codex.views.opds.const import BLANK_TITLE, DEFAULT_PARAMS
from codex.views.opds.v2.feed.groups import OPDS2FeedGroupsView

_ORDER_BY_SUBTITLE_MAP = MappingProxyType(
    {"bookmark_updated_at": "read", "created_at": "added", "date": "published"}
)


class OPDS2FeedView(OPDS2FeedGroupsView):
    """OPDS 2.0 Feed."""

    serializer_class = OPDS2FeedSerializer
    input_serializer_class = OPDSSettingsSerializer

    IS_START_PAGE: bool = False

    def _subtitle(self):
        """Subtitle for main feed."""
        # Add filters and order
        parts = []
        qps = self.request.GET
        if filters := qps.get("filters"):
            filters = urllib.parse.unquote(filters)
            if bf := json.loads(filters).get("bookmark", ""):
                bf = "reading" if bf == "IN_PROGRESS" else bf.lower()
            parts.append(bf)
        if q := qps.get("query"):
            search_query = urllib.parse.unquote(q)
            parts.append(search_query)
        if (order_by := qps.get("orderBy")) and order_by != "sort_name":
            order_by = _ORDER_BY_SUBTITLE_MAP.get(order_by, order_by)
            parts.append(order_by)
        if (order_reverse := qps.get("orderReverse")) and order_reverse not in FALSY:
            parts.append("desc")
        return ", ".join(parts) if parts else ""

    def _title(self, browser_title: Mapping[str, str]):
        """Create the feed title."""
        result = self.request.GET.get("title", "")
        if not result and browser_title:
            parent_name = browser_title.get("parent_name", None)
            pks = self.kwargs["pks"]
            if not parent_name and not pks:
                parent_name = "All"
            group_name = browser_title.get("group_name")
            result = " ".join(filter(None, (parent_name, group_name))).strip()

        if not result:
            result = BLANK_TITLE

        return result

    def _feed_metadata(self, title: str, total_count: int, mtime: datetime | None):
        number_of_items = total_count
        current_page = self.kwargs.get("page")
        md = {
            "title": title,
            "number_of_items": number_of_items,
            "items_per_page": MAX_OBJ_PER_PAGE,
            "current_page": current_page,
        }
        if mtime:
            md["modified"] = mtime
        if subtitle := self._subtitle():
            md["subtitle"] = subtitle
        return MappingProxyType(md)

    def _feed_navigation_and_groups(
        self,
        group_qs: QuerySet,
        book_qs: QuerySet,
        zero_pad: int | None,
        title: str,
    ):
        groups = []
        navigation = []
        top_groups = self._get_top_groups()
        if self.IS_START_PAGE:
            groups += self._get_ordered_groups()
            first_top_group = next(iter(top_groups), {})
            navigation = first_top_group.get("navigation", [])
            publications = []
        else:
            # Move the first group's navigation to become the feed navigation.
            # The feed navigation is titled "Browse"" in Stump
            zero_pad = zero_pad if zero_pad else 0
            regular_groups = self._get_groups(group_qs, book_qs, title, zero_pad)
            first_regular_group = next(iter(regular_groups), {})
            navigation = first_regular_group.pop("navigation", [])

            groups += regular_groups
            groups += top_groups
            groups += self._get_facets()
            groups += self._get_start_groups()

            publications = first_regular_group.pop("publications", [])
        return tuple(navigation), tuple(groups), tuple(publications)

    @staticmethod
    def _update_feed_modified(feed_metadata: Mapping, groups: Iterable[Mapping]):  # noqa: ARG004
        return feed_metadata

    @override
    def get_object(self):
        """Get the browser page and serialize it for this subclass."""
        group_qs, book_qs, _, total_count, zero_pad, mtime = self.group_and_books
        # convert browser_page into opds pagej
        browser_title = self.get_browser_page_title()
        title = "Start" if self.IS_START_PAGE else self._title(browser_title)

        # opds page
        metadata = self._feed_metadata(title, total_count, mtime)

        # links
        up_route = self.get_last_route()
        links = tuple(self.get_links(up_route))

        # Navigation & Groups
        navigation, groups, publications = self._feed_navigation_and_groups(
            group_qs, book_qs, zero_pad, title
        )
        metadata = self._update_feed_modified(metadata, groups)

        feed = {
            "metadata": metadata,
            "links": links,
        }
        if navigation:
            feed["navigation"] = navigation
        if groups:
            feed["groups"] = groups
        if publications:
            feed["publications"] = publications

        return MappingProxyType(feed)

    @override
    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        self.mark_user_active()
        return Response(serializer.data)


class OPDS2StartView(OPDS2FeedView):
    """Start View."""

    IS_START_PAGE = True

    def __init__(self, *args, **kwargs):
        """Reset all params."""
        super().__init__(*args, **kwargs)
        self.set_params(DEFAULT_PARAMS)

    @override
    @staticmethod
    def _update_feed_modified(feed_metadata: Mapping, groups: Iterable[Mapping]):
        max_modified = EPOCH_START
        for group in groups:
            for publication in group.get("publications", []):
                modified = publication.get("metadata", {}).get("modified", EPOCH_START)
                max_modified = max(max_modified, modified)
        if max_modified != feed_metadata["modified"]:
            feed_metadata = dict(feed_metadata)
            feed_metadata["modified"] = max_modified
        return feed_metadata

    @override
    @extend_schema(
        parameters=[OPDS2FeedView.input_serializer_class],
        operation_id="opds_2.0_start_retrieve",
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

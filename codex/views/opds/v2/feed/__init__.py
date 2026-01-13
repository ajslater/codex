"""OPDS v2.0 Feed."""

import json
import urllib.parse
from types import MappingProxyType

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v2.feed import OPDS2FeedSerializer
from codex.settings import FALSY, MAX_OBJ_PER_PAGE
from codex.views.opds.const import BLANK_TITLE
from codex.views.opds.v2.feed.groups import OPDS2FeedGroupsView

_ORDER_BY_MAP = MappingProxyType(
    {"bookmark_updated_at": "read", "created_at": "added", "date": "published"}
)


class OPDS2FeedView(OPDS2FeedGroupsView):
    """OPDS 2.0 Feed."""

    TARGET: str = "opds2"
    throttle_scope = "opds"

    serializer_class: type[BaseSerializer] | None = OPDS2FeedSerializer
    input_serializer_class: type[OPDSSettingsSerializer] = OPDSSettingsSerializer  # pyright: ignore[reportIncompatibleVariableOverride]

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
        if (order_by := qps.get("orderBy")) and order_by != "sort_name":
            order_by = _ORDER_BY_MAP.get(order_by, order_by)
            parts.append(order_by)
        if (order_reverse := qps.get("orderReverse")) and order_reverse not in FALSY:
            parts.append("desc")
        return f" ({','.join(parts)})" if parts else ""

    def _title(self, browser_title):
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

        result += self._subtitle()
        return result

    @override
    def get_object(self):
        """Get the browser page and serialize it for this subclass."""
        group_qs, book_qs, _, total_count, zero_pad, mtime = self.group_and_books
        title = self.get_browser_page_title()
        # convert browser_page into opds page

        # opds page
        title = self._title(title)
        zero_pad = zero_pad if zero_pad else 0

        # Move the first group's navigation to become the feed navigation.
        # The feed navigation is titled "Browse"" in Stump
        regular_groups = self._get_groups(group_qs, book_qs, title, zero_pad)
        first_regular_group = next(iter(regular_groups), {})
        navigation = first_regular_group.pop("navigation", [])

        # opds groups
        groups = []
        if first_regular_group.get("publications"):
            groups += regular_groups
        og = self._get_ordered_groups()
        groups += og
        groups += self._get_top_groups()
        groups += self._get_facets()
        groups += self._get_start_groups()

        number_of_items = total_count
        current_page = self.kwargs.get("page")
        up_route = self.get_last_route()
        links = self.get_links(up_route)

        feed = {
            "metadata": {
                "title": title,
                "modified": mtime,
                "number_of_items": number_of_items,
                "items_per_page": MAX_OBJ_PER_PAGE,
                "current_page": current_page,
            },
            "links": links,
        }
        if navigation:
            feed["navigation"] = navigation
        if groups:
            feed["groups"] = groups

        return MappingProxyType(feed)

    @override
    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        self.mark_user_active()
        return Response(serializer.data)

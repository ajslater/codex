"""Links methods for OPDS v2.0 Feed."""

import json
from copy import deepcopy
from datetime import datetime
from urllib.parse import parse_qsl, urlparse

from django.db.models import QuerySet
from typing_extensions import override

from codex.settings import FALSY
from codex.views.opds.const import BookmarkFilters, MimeType, Rel, UserAgentNames
from codex.views.opds.feed import OPDSBrowserView
from codex.views.opds.v2.const import HrefData, LinkData
from codex.views.opds.v2.href import OPDS2HrefMixin

_BOOKMARK_FILTERS_NONE_STR = json.dumps(dict(BookmarkFilters.NONE))


class OPDS2LinksView(OPDS2HrefMixin, OPDSBrowserView):
    """Links methods for OPDS 2.0 Feed."""

    TARGET = "opds2"
    throttle_scope = "opds"

    def __init__(self, *args, **kwargs):
        """Initialize properties."""
        super().__init__(*args, **kwargs)
        self._num_pages: int | None = None
        self._group_and_books: (
            tuple[QuerySet, QuerySet, int, int, int | None, datetime | None] | None
        ) = None
        self._user_agent_name: str | None = None

    @property
    def group_and_books(
        self,
    ) -> tuple[QuerySet, QuerySet, int, int, int | None, datetime | None]:
        """Memoize Group And Books for num_pages."""
        # group_qs, book_qs, num_pages, total_count, zero_pad, mtime
        if self._group_and_books is None:
            self._group_and_books = self._get_group_and_books()
        return self._group_and_books

    @property
    @override
    def num_pages(self) -> int:
        """Memoize num_pages."""
        if self._num_pages is None:
            self._num_pages = self.group_and_books[2]
        return self._num_pages

    @staticmethod
    def _link_attributes(data, link):
        """Add attributes to link."""
        if data.title:
            link["title"] = data.title
        if data.href_data.template:
            link["templated"] = True
        if data.height:
            link["height"] = data.height
        if data.width:
            link["width"] = data.width
        if data.size:
            link["size"] = data.size

    @staticmethod
    def _link_properties(data, link):
        """Add properties attribute to link."""
        if data.num_items or data.authenticate:
            link["properties"] = {}
        if data.num_items:
            link["properties"]["number_of_items"] = data.num_items
        if data.authenticate:
            link["properties"]["authenticate"] = data.authenticate

    def link(self, data):
        """Create a link element."""
        if data.href:
            href = data.href
        else:
            href = self.href(data.href_data)
            if not href:
                return None
        if self.user_agent_name in UserAgentNames.REQUIRE_ABSOLUTE_URL:
            href = self.request.build_absolute_uri(href)
        mime_type = data.mime_type if data.mime_type else MimeType.OPDS_JSON
        link = {"href": href, "rel": data.rel, "type": mime_type}
        self._link_attributes(data, link)
        self._link_properties(data, link)
        return link

    @staticmethod
    def _normalize_query_params(qps_dict):
        if qps_dict.get("orderBy") == "sort_name":
            qps_dict.pop("orderBy", None)
        if qps_dict.get("orderReverse", "").lower() in FALSY:
            qps_dict.pop("orderReverse", None)
        if qps_dict.get("filters", {}) == _BOOKMARK_FILTERS_NONE_STR:
            qps_dict.pop("filters")
        return frozenset(qps_dict.items())

    def _is_self_link(self, href):
        """Return if the path and query params match the current request."""
        req_qps = deepcopy(self.request.GET)
        req_qps = self._normalize_query_params(req_qps)

        # This is inefficient since i construct the query_params before this
        # but it's difficult to get the final query params for all constructions.
        parts = urlparse(href)
        href_qps = dict(parse_qsl(parts.query))
        href_qps = self._normalize_query_params(href_qps)

        return self.request.path == parts.path and req_qps == href_qps

    def link_aggregate(self, link_dict, link):
        """Aggregate links into a dict to combine rels into an array."""
        if not link:
            return
        href = link["href"]
        rel = link.pop("rel")
        if href in link_dict:
            link_dict[href]["rels"].add(rel)
        else:
            link_dict[href] = link
            link_dict[href]["rels"] = {rel}

            if self._is_self_link(href):
                link_dict[href]["rels"].add(Rel.SELF)

    @staticmethod
    def get_links_from_dict(link_dict):
        """Produce the final links list from the aggregate dict."""
        final_links = []
        for link in link_dict.values():
            # rel can be a list or or a string.
            rels = sorted(link.pop("rels"))
            rel = rels if len(rels) > 1 else rels[0]
            link["rel"] = rel
            final_links.append(link)
        return final_links

    def link_self(self):
        """Create the self link for this page."""
        href_data = HrefData(self.kwargs, dict(self.request.GET))
        link_data = LinkData(Rel.SELF, href_data)
        return self.link(link_data)

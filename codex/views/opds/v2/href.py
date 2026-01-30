"""Href methods for OPDS v2.0 Feed."""

import json
from collections.abc import Mapping
from itertools import chain

from caseconverter import camelcase
from django.urls import reverse

from codex.settings import DEBUG
from codex.views.opds.const import UserAgentNames
from codex.views.util import pop_name


class OPDS2HrefMixin:
    """Create links method."""

    @property
    def num_pages(self) -> int:
        """Dummy."""
        return 1

    def _href_page_validate(self, kwargs, data):
        """Validate the page bounds."""
        min_page = min(1, 1 if data.min_page is None else data.min_page)
        max_page = max(1, self.num_pages if data.max_page is None else data.max_page)
        page = int(kwargs["page"])
        return page >= min_page and page <= max_page

    def _href_update_query_params(self, data):
        """Update the query params."""
        # Merge query_params and camelCase keys
        qps_maps = []
        if data.inherit_query_params:
            qps_maps.append(self.request.GET)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if data.query_params:
            qps_maps.append(data.query_params)
        query = {}
        for key, val in chain(*(d.items() for d in qps_maps)):
            query[camelcase(key)] = val

        # Stringify filters value
        if (filters := query.get("filters")) and isinstance(filters, Mapping):
            query["filters"] = json.dumps(dict(filters))

        return query

    def href(self, data):
        """Create an href."""
        url_name = data.url_name if data.url_name else "opds:v2:feed"
        kwargs = data.kwargs if data.kwargs is not None else self.kwargs  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if "page" in kwargs and not self._href_page_validate(kwargs, data):
            return None

        kwargs = pop_name(kwargs)
        query = self._href_update_query_params(data)
        href = reverse(url_name, kwargs=kwargs, query=query)
        if DEBUG or self.user_agent_name in UserAgentNames.REQUIRE_ABSOLUTE_URL:  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            href = self.request.build_absolute_uri(href)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if template := data.template:
            parts = href.split("?")
            if len(parts) > 1:
                template += "&"
            href = template.join(parts)
        return href

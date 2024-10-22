"""Href methods for OPDS v2.0 Feed."""

from abc import ABC
from dataclasses import dataclass

from django.urls import reverse
from rest_framework.views import APIView

from codex.views.opds.util import update_href_query_params
from codex.views.util import pop_name


@dataclass
class HrefData:
    """Data for creating hrefs."""

    kwargs: dict | None = None
    query_params: dict | None = None
    absolute_query_params: bool = False
    url_name: str | None = None
    min_page: int | None = None
    max_page: int | None = None


class OPDS2HrefMixin(APIView, ABC):
    """Create links method."""

    @property
    def num_pages(self) -> int:
        """Dummy."""
        return 1

    def _href_page_validate(self, kwargs, data):
        """Validate the page bounds."""
        min_page = 1 if data.min_page is None else data.min_page
        max_page = self.num_pages if data.max_page is None else data.max_page
        page = int(kwargs["page"])
        return page >= min_page and page <= max_page

    def _href_update_query_params(self, href, data):
        """Update the query params."""
        if data.absolute_query_params and data.query_params:
            href = update_href_query_params(href, data.query_params)
        elif hasattr(self, "request"):
            # if request link and not init static links
            href = update_href_query_params(
                href, self.request.GET, new_query_params=data.query_params
            )
        return href

    def href(self, data):
        """Create an href."""
        url_name = data.url_name if data.url_name else "opds:v2:feed"
        kwargs = data.kwargs if data.kwargs is not None else self.kwargs
        if "page" in kwargs and not self._href_page_validate(kwargs, data):
            return None

        kwargs = pop_name(kwargs)
        href = reverse(url_name, kwargs=kwargs)
        return self._href_update_query_params(href, data)

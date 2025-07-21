"""Href methods for OPDS v2.0 Feed."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.urls import reverse

from codex.views.util import pop_name

if TYPE_CHECKING:
    from rest_framework.request import Request


@dataclass
class HrefData:
    """Data for creating hrefs."""

    kwargs: dict | None = None
    query_params: dict | None = None
    absolute_query_params: bool = False
    url_name: str | None = None
    min_page: int | None = None
    max_page: int | None = None


class OPDS2HrefMixin:
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

    def _href_update_query_params(self, data):
        """Update the query params."""
        query = {}
        if data.absolute_query_params and data.query_params:
            query.update(data.query_params)
        elif hasattr(self, "request"):
            # if request link and not init static links
            if TYPE_CHECKING:
                self.request: Request  # pyright: ignore[reportUninitializedInstanceVariable]
            query.update(self.request.GET)
            query.update(data.query_params)
        return query

    def href(self, data):
        """Create an href."""
        url_name = data.url_name if data.url_name else "opds:v2:feed"
        if TYPE_CHECKING:
            self.kwargs: dict  # pyright: ignore[reportUninitializedInstanceVariable]
        kwargs = data.kwargs if data.kwargs is not None else self.kwargs
        if "page" in kwargs and not self._href_page_validate(kwargs, data):
            return None

        kwargs = pop_name(kwargs)
        query = self._href_update_query_params(data)
        return reverse(url_name, kwargs=kwargs, query=query)

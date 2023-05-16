"""Links methods for OPDS v2.0 Feed."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl, urlparse

from django.urls import reverse

from codex.views.browser.browser import BrowserView
from codex.views.opds.const import FALSY, MimeType, Rel
from codex.views.opds.util import update_href_query_params


@dataclass
class HrefData:
    """Data for creating hrefs."""

    kwargs: Optional[dict] = None
    query_params: Optional[dict] = None
    absolute_query_params: bool = False
    url_name: Optional[str] = None
    min_page: Optional[int] = None
    max_page: Optional[int] = None


@dataclass
class LinkData:
    """Data for creating links."""

    rel: str
    href_data: HrefData
    title: Optional[str] = None
    mime_type: Optional[str] = None
    template: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None
    href: Optional[str] = None
    num_items: Optional[int] = None


class LinksMixin(BrowserView):
    """Links methods for OPDS 2.0 Feed."""

    num_pages = 0  # For pyright. Overwritten every run.

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
                href, self.request.query_params, new_query_params=data.query_params
            )
        return href

    def _href(self, data):
        """Create an href."""
        url_name = data.url_name if data.url_name else "opds:v2:feed"
        kwargs = data.kwargs if data.kwargs is not None else self.kwargs
        if "page" in kwargs and not self._href_page_validate(kwargs, data):
            return None

        href = reverse(url_name, kwargs=kwargs)
        return self._href_update_query_params(href, data)

    def link(self, data):
        """Create a link element."""
        if data.href:
            href = data.href
        else:
            href = self._href(data.href_data)
            if not href:
                return None
        mime_type = data.mime_type if data.mime_type else MimeType.OPDS_JSON
        link = {"href": href, "rel": data.rel, "type": mime_type}
        if data.title:
            link["title"] = data.title
        if data.template:
            link["templated"] = True
            link["href"] += data.template
        if data.height:
            link["height"] = data.height
        if data.width:
            link["width"] = data.width
        if data.num_items:
            link["properties"] = {"number_of_items": data.num_items}
        return link

    @staticmethod
    def _normalize_query_params(qps_dict):
        if qps_dict.get("orderBy") == "sort_name":
            qps_dict.pop("orderBy")
        if qps_dict.get("orderReverse") == FALSY:
            qps_dict.pop("orderReverse")
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
        href_data = HrefData(
            self.kwargs, dict(self.request.GET), absolute_query_params=True
        )
        link_data = LinkData(Rel.SELF, href_data)
        return self.link(link_data)

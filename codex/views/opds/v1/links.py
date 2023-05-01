"""OPDS 1 Links methods."""
from django.urls import reverse
from django.utils.http import urlencode

from codex.logger.logging import get_logger
from codex.views.opds.const import MimeType, Rel
from codex.views.opds.util import update_href_query_params
from codex.views.opds.v1.const import (  # TODO move here?
    OPDSLink,
    RootTopLinks,
    TopLinks,
)
from codex.views.opds.v1.entry import OPDS1Entry, OPDS1EntryObject
from codex.views.opds.v1.facets import FacetsMixin

LOG = get_logger(__name__)


class LinksMixin(FacetsMixin):
    """OPDS 1 Links methods."""

    # overwritten in get_object()
    is_aq_feed = False

    def _nav_link(self, kwargs, rel):
        href = reverse("opds:v1:feed", kwargs={**kwargs})
        href = update_href_query_params(href, self.request.query_params)
        return OPDSLink(rel, href, MimeType.NAV)

    def _top_link(self, top_link):
        href = reverse("opds:v1:feed", kwargs={**top_link.kwargs, "page": 1})
        if top_link.query_params:
            href += "?" + urlencode(top_link.query_params, doseq=True)
        return OPDSLink(top_link.rel, href, top_link.mime_type)

    def _root_nav_links(self):
        """Navigation Root Links."""
        links = []
        if route := self.obj.get("up_route"):
            links += [self._nav_link(route, Rel.UP)]
        page = self.kwargs.get("page", 1)
        if page > 1:
            route = {**self.kwargs, "page": page - 1}
            links += [self._nav_link(route, Rel.PREV)]
        if page < self.obj.get("num_pages", 1):
            route = {**self.kwargs, "page": page + 1}
            links += [self._nav_link(route, Rel.NEXT)]
        return links

    def is_top_link_displayed(self, top_link):
        """Determine if this top link should be displayed."""
        for key, value in top_link.kwargs.items():
            if str(self.kwargs.get(key)) != str(value):
                return False

        for key, value in top_link.query_params.items():
            if str(self.request.query_params.get(key)) != str(value):
                return False

        return True

    @property
    def links(self):
        """Create all the links."""
        links = []
        try:
            mime_type = MimeType.ACQUISITION if self.is_aq_feed else MimeType.NAV
            links += [
                OPDSLink("self", self.request.get_full_path(), mime_type),
                OPDSLink(
                    Rel.AUTHENTICATION,
                    reverse("opds:authentication:v1"),
                    MimeType.AUTHENTICATION,
                ),
                OPDSLink(
                    "search", reverse("opds:v1:opensearch_v1"), MimeType.OPENSEARCH
                ),
            ]
            links += self._root_nav_links()
            if self.use_facets:
                for top_link in TopLinks.ALL + RootTopLinks.ALL:
                    if not self.is_top_link_displayed(top_link):
                        links += [self._top_link(top_link)]
                if facets := self.facets():
                    links += facets
        except Exception as exc:
            LOG.exception(exc)
        return links

    def _top_link_entry(self, top_link):
        """Create a entry instead of a facet."""
        name = " ".join(filter(None, (top_link.glyph, top_link.title)))
        entry_obj = OPDS1EntryObject(
            **top_link.kwargs,
            name=name,
            summary=top_link.desc,
        )
        issue_max = self.obj.get("issue_max")
        data = (self.acquisition_groups, issue_max, False)
        return OPDS1Entry(entry_obj, top_link.query_params, data)

    def add_top_links(self, top_links):
        """Add a list of top links as entries if they should be enabled."""
        entries = []
        for tl in top_links:
            if not self.is_top_link_displayed(tl):
                entries += [self._top_link_entry(tl)]
        return entries

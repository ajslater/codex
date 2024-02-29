"""OPDS v1 Links methods."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import simplejson as json
from django.urls import reverse

from codex.logger.logging import get_logger
from codex.views.opds.const import MimeType, Rel
from codex.views.opds.util import update_href_query_params
from codex.views.opds.v1.data import OPDS1Link
from codex.views.opds.v1.entry.data import OPDS1EntryData, OPDS1EntryObject
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.opds.v1.facets import FacetsMixin

LOG = get_logger(__name__)


class TopRoutes:
    """Routes for top groups."""

    PUBLISHER = MappingProxyType({"group": "p", "pk": 0, "page": 1})
    SERIES = MappingProxyType({"group": "s", "pk": 0, "page": 1})
    FOLDER = MappingProxyType({"group": "f", "pk": 0, "page": 1})
    ROOT = MappingProxyType({"group": "r", "pk": 0, "page": 1})
    STORY_ARC = MappingProxyType({"group": "a", "pk": 0, "page": 1})


@dataclass
class TopLink:
    """A non standard root link when facets are unsupported."""

    kwargs: Mapping
    rel: str
    mime_type: str
    query_params: defaultdict[str, str | bool | int]
    glyph: str
    title: str
    desc: str


class TopLinks:
    """Top link definitions."""

    START = TopLink(
        TopRoutes.ROOT,
        Rel.START,
        MimeType.NAV,
        defaultdict(),
        "⌂",
        "Start of the catalog",
        "",
    )
    ALL = (START,)


class RootTopLinks:
    """Top Links that only appear at the root."""

    NEW = TopLink(
        TopRoutes.SERIES,
        Rel.SORT_NEW,
        MimeType.ACQUISITION,
        defaultdict(
            None, {"orderBy": "created_at", "orderReverse": True, "limit": 100}
        ),
        "📥",
        "Recently Added",
        "",
    )
    FEATURED = TopLink(
        TopRoutes.SERIES,
        Rel.FEATURED,
        MimeType.NAV,
        defaultdict(
            None,
            {
                "orderBy": "date",
                "filters": json.dumps({"bookmark": "UNREAD"}),
                "limit": 100,
            },
        ),
        "📚",
        "Oldest Unread",
        "Unread issues, oldest published first",
    )
    LAST_READ = TopLink(
        TopRoutes.SERIES,
        Rel.POPULAR,
        MimeType.NAV,
        defaultdict(
            None, {"orderBy": "bookmark_updated_at", "orderReverse": True, "limit": 100}
        ),
        "👀",
        "Last Read",
        "Last Read issues, recently read first.",
    )
    ALL = (NEW, FEATURED, LAST_READ)


class LinksMixin(FacetsMixin):
    """OPDS 1 Links methods."""

    # overwritten in get_object()
    DEFAULT_ROUTE_NAME = "opds:v1:feed"
    is_aq_feed = False

    def is_top_link_displayed(self, top_link):
        """Determine if this top link should be displayed."""
        for key, value in top_link.kwargs.items():
            if str(self.kwargs.get(key)) != str(value):
                return False

        for key, value in top_link.query_params.items():
            if str(self.request.query_params.get(key)) != str(value):
                return False

        return True

    def _link(self, kwargs, rel, query_params=None, mime_type=MimeType.NAV):
        """Create a link."""
        if query_params is None:
            query_params = self.request.query_params
        href = reverse("opds:v1:feed", kwargs=kwargs)
        href = update_href_query_params(href, query_params)
        return OPDS1Link(rel, href, mime_type)

    def _top_link(self, top_link):
        """Create a link from a top link."""
        return self._link(
            top_link.kwargs, top_link.rel, top_link.query_params, top_link.mime_type
        )

    def _root_links(self):
        """Navigation Root Links."""
        links = []
        if route := self.obj.get("up_route"):
            links += [self._link(route, Rel.UP)]
        page = self.kwargs.get("page", 1)
        if page > 1:
            route = {**self.kwargs, "page": page - 1}
            links += [self._link(route, Rel.PREV)]
        if page < self.obj.get("num_pages", 1):
            route = {**self.kwargs, "page": page + 1}
            links += [self._link(route, Rel.NEXT)]
        return links

    @property
    def links(self):
        """Create all the links."""
        links = []
        try:
            mime_type = MimeType.ACQUISITION if self.is_aq_feed else MimeType.NAV
            links += [
                OPDS1Link("self", self.request.get_full_path(), mime_type),
                OPDS1Link(
                    Rel.AUTHENTICATION,
                    reverse("opds:authentication:v1"),
                    MimeType.AUTHENTICATION,
                ),
                OPDS1Link(
                    "search", reverse("opds:v1:opensearch_v1"), MimeType.OPENSEARCH
                ),
            ]
            links += self._root_links()
            if self.use_facets:
                for top_link in TopLinks.ALL + RootTopLinks.ALL:
                    if not self.is_top_link_displayed(top_link):
                        links += [self._top_link(top_link)]
                if facets := self.facets():
                    links += facets
        except Exception:
            LOG.exception("Getting OPDS v1 links")
        return links

    def _top_link_entry(self, top_link):
        """Create a entry instead of a facet."""
        name = " ".join(filter(None, (top_link.glyph, top_link.title)))
        entry_obj = OPDS1EntryObject(
            group=top_link.kwargs["group"],
            pk=top_link.kwargs["pk"],
            name=name,
            summary=top_link.desc,
        )
        issue_number_max = self.obj.get("issue_number_max", 0)
        data = OPDS1EntryData(
            self.acquisition_groups, issue_number_max, False, self.mime_type_map
        )
        return OPDS1Entry(entry_obj, top_link.query_params, data)

    def add_top_links(self, top_links):
        """Add a list of top links as entries if they should be enabled."""
        entries = []
        for tl in top_links:
            if not self.is_top_link_displayed(tl):
                entries += [self._top_link_entry(tl)]
        return entries

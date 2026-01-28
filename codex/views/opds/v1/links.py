"""OPDS v1 Links methods."""

from django.urls import reverse
from loguru import logger

from codex.views.opds.const import MimeType, Rel
from codex.views.opds.v1.const import (
    OPDS1EntryData,
    OPDS1EntryObject,
    OPDS1Link,
    RootTopLinks,
    TopLink,
    TopLinks,
)
from codex.views.opds.v1.entry.entry import OPDS1Entry
from codex.views.opds.v1.facets import OPDS1FacetsView
from codex.views.util import pop_name


class OPDS1LinksView(OPDS1FacetsView):
    """OPDS 1 Links methods."""

    def is_top_link_displayed(self, top_link):
        """Determine if this top link should be displayed."""
        for key, value in top_link.kwargs.items():
            if str(self.kwargs.get(key)) != str(value):
                return False

        for key, value in top_link.query_params.items():
            if str(self.request.GET.get(key)) != str(value):
                return False

        return True

    def _link(self, kwargs, rel, query_params=None, mime_type=MimeType.NAV):
        """Create a link."""
        if query_params is None:
            query_params = self.request.GET
        kwargs = pop_name(kwargs)
        href = reverse("opds:v1:feed", kwargs=kwargs, query=query_params)
        return OPDS1Link(rel, href, mime_type)

    def _top_link(self, top_link):
        """Create a link from a top link."""
        return self._link(
            top_link.kwargs, top_link.rel, top_link.query_params, top_link.mime_type
        )

    def _root_links(self):
        """Navigation Root Links."""
        links = []
        if (
            (up_route := self.get_last_route())
            and (pks := up_route.get("pks", []))
            and 0 not in pks
        ):
            links += [self._link(up_route, Rel.UP)]
        page = self.kwargs.get("page", 1)
        if page > 1:
            prev_route = {**self.kwargs, "page": page - 1}
            links += [self._link(prev_route, Rel.PREV)]
        if page < self.obj.get("num_pages", 1):
            next_route = {**self.kwargs, "page": page + 1}
            links += [self._link(next_route, Rel.NEXT)]
        return links

    def _links_start_page_links(self):
        links = []
        if not self.IS_START_PAGE:
            return links
        links += [
            OPDS1Link(Rel.ALTERNATE, reverse("opds:v2:start"), MimeType.OPDS_JSON)
        ]
        return links

    def _links_facets(self):
        links = []
        if not self.use_facets:
            return links
        for top_link in TopLinks.ALL + RootTopLinks.ALL:
            if not self.is_top_link_displayed(top_link):
                links += [self._top_link(top_link)]
        if facets := self.facets(entries=False):
            links += facets
        return links

    @property
    def links(self):
        """Create all the links."""
        links = []
        try:
            self_mime_type = (
                MimeType.ACQUISITION if self.is_opds_acquisition else MimeType.NAV
            )
            links += [
                OPDS1Link("self", self.request.get_full_path(), self_mime_type),
                OPDS1Link(
                    Rel.AUTHENTICATION,
                    reverse("opds:auth:v1"),
                    MimeType.AUTHENTICATION,
                ),
                OPDS1Link(Rel.START, reverse("opds:v1:start"), MimeType.NAV),
                OPDS1Link(
                    Rel.SEARCH, reverse("opds:v1:opensearch_v1"), MimeType.OPENSEARCH
                ),
            ]
            links += self._links_start_page_links()
            links += self._root_links()
            links += self._links_facets()
        except Exception:
            logger.exception("Getting OPDS v1 links")
        return links

    def _top_link_entry(self, top_link):
        """Create a entry instead of a facet."""
        name = " ".join(filter(None, (top_link.glyph, top_link.title)))
        entry_obj = OPDS1EntryObject(
            group=top_link.kwargs["group"],
            ids=top_link.kwargs["pks"],
            name=name,
            summary=top_link.desc,
        )
        zero_pad: int = self.obj["zero_pad"]
        data = OPDS1EntryData(
            self.opds_acquisition_groups,
            zero_pad,
            metadata=False,
            mime_type_map=self.mime_type_map,
        )
        return OPDS1Entry(
            entry_obj, top_link.query_params, data, title_filename_fallback=False
        )

    def add_start_link(self):
        """Add the start link."""
        top_link: TopLink = TopLinks.START
        name = " ".join(filter(None, (top_link.glyph, top_link.title)))
        entry_obj = OPDS1EntryObject(
            name=name, summary=top_link.desc, url_name=top_link.url_name
        )

        data = OPDS1EntryData(
            frozenset(), 0, metadata=False, mime_type_map=self.mime_type_map
        )
        return [OPDS1Entry(entry_obj, {}, data, title_filename_fallback=False)]

    def add_top_links(self, top_links):
        """Add a list of top links as entries if they should be enabled."""
        entries = []
        for tl in top_links:
            if not self.is_top_link_displayed(tl):
                entries += [self._top_link_entry(tl)]
        return entries

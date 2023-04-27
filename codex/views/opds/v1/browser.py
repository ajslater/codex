"""OPDS browser."""

from datetime import datetime, timezone

from django.urls import reverse
from django.utils.http import urlencode
from drf_spectacular.utils import extend_schema
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.serializers.opds.v1 import (
    OPDS1TemplateSerializer,
)
from codex.views.browser.browser import BrowserView
from codex.views.opds.const import (
    BLANK_TITLE,
    FALSY,
    MimeType,
    Rel,
)
from codex.views.opds.util import update_href_query_params
from codex.views.opds.v1.entry import OPDS1Entry, OPDS1EntryObject
from codex.views.opds.v1.util import (
    DEFAULT_FACETS,
    Facet,
    FacetGroups,
    OPDSLink,
    OpdsNs,
    RootFacetGroups,
    RootTopLinks,
    TopLinks,
    UserAgents,
)
from codex.views.template import CodexXMLTemplateView

LOG = get_logger(__name__)


class OPDS1BrowserView(BrowserView, CodexXMLTemplateView):
    """The main opds browser."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)
    template_name = "opds/index.xml"
    serializer_class = OPDS1TemplateSerializer

    @property
    def opds_ns(self):
        """Dynamic opds namespace."""
        try:
            return OpdsNs.ACQUISITION if self.is_aq_feed else OpdsNs.CATALOG
        except Exception as exc:
            LOG.exception(exc)

    @property
    def id_tag(self):
        """Feed id is the url."""
        try:
            return self.request.build_absolute_uri()
        except Exception as exc:
            LOG.exception(exc)

    @property
    def title(self):
        """Create the feed title."""
        result = ""
        try:
            if browser_title := self.obj.get("browser_title"):
                parent_name = browser_title.get("parent_name", "All")
                if not parent_name and self.kwargs.get("pk") == 0:
                    parent_name = "All"
                group_name = browser_title.get("group_name")
                result = " ".join(filter(None, (parent_name, group_name))).strip()

            if not result:
                result = BLANK_TITLE
        except Exception as exc:
            LOG.exception(exc)
        return result

    @property
    def updated(self):
        """Hack in feed update time from cover timestamp."""
        try:
            if ts := self.obj.get("covers_timestamp"):
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception as exc:
            LOG.exception(exc)

    @property
    def items_per_page(self):
        """Return opensearch:itemsPerPage."""
        try:
            if self.params.get("q"):
                return self.MAX_OBJ_PER_PAGE
        except Exception as exc:
            LOG.exception(exc)

    @property
    def total_results(self):
        """Return opensearch:totalResults."""
        try:
            if self.params.get("q"):
                return self.obj.get("total_count", 0)
        except Exception as exc:
            LOG.exception(exc)

    def _facet(self, kwargs, facet_group, facet_title, new_query_params):
        href = reverse("opds:v1:browser", kwargs=kwargs)
        facet_active = False
        for key, val in new_query_params.items():
            if self.request.query_params.get(key) == val:
                facet_active = True
                break
        href = update_href_query_params(
            href, self.request.query_params, new_query_params
        )

        title = " ".join(filter(None, (facet_group.title_prefix, facet_title))).strip()
        return OPDSLink(
            Rel.FACET,
            href,
            MimeType.NAV,
            title=title,
            facet_group=facet_group.query_param,
            facet_active=facet_active,
        )

    def _facet_entry(self, item, facet_group, facet, query_params):
        name = " ".join(
            filter(None, (facet_group.glyph, facet_group.title_prefix, facet.title))
        ).strip()
        entry_obj = OPDS1EntryObject(
            group=item.get("group"),
            pk=item.get("pk"),
            name=name,
            query_params=query_params,
        )
        issue_max = self.obj.get("issue_max")
        data = (self.acquisition_groups, issue_max, False)
        return OPDS1Entry(entry_obj, {**self.request.query_params}, data)

    def _is_facet_active(self, facet_group, facet):
        compare = [facet.value]
        default_val = DEFAULT_FACETS.get(facet_group.query_param)
        if facet.value == default_val:
            compare += [None]
        return self.request.query_params.get(facet_group.query_param) in compare

    def _facet_or_facet_entry(self, facet_group, facet, entries):
        # This logic preempts facet:activeFacet but no one uses it.
        # don't add default facets if in default mode.
        if self._is_facet_active(facet_group, facet):
            return None

        group = self.kwargs.get("group")
        if (
            facet_group.query_param == "topGroup"
            and (group == "f" and facet.value != "f")
            or (group != "f" and facet.value == "f")
        ):
            kwargs = {"group": facet.value, "pk": 0, "page": 1}
        else:
            kwargs = self.kwargs

        qps = {facet_group.query_param: facet.value}
        if entries and self.kwargs.get("page") == 1:
            facet = self._facet_entry(kwargs, facet_group, facet, qps)
        else:
            facet = self._facet(kwargs, facet_group, facet.title, qps)
        return facet

    def _facet_group(self, facet_group, entries):
        facets = []
        for facet in facet_group.facets:
            if facet_obj := self._facet_or_facet_entry(facet_group, facet, entries):
                facets += [facet_obj]
        return facets

    def _facets(self, entries=False, root=True):
        facets = []
        if not self.skip_order_facets:
            facets += self._facet_group(FacetGroups.ORDER_BY, entries)
            facets += self._facet_group(FacetGroups.ORDER_REVERSE, entries)
        if root:
            facets += self._facet_group(RootFacetGroups.TOP_GROUP, entries)
            if facet_obj := self._facet_or_facet_entry(
                RootFacetGroups.TOP_GROUP, Facet("f", "Folder View"), entries
            ):
                facets += [facet_obj]
        return facets

    def _nav_link(self, kwargs, rel):
        href = reverse("opds:v1:browser", kwargs={**kwargs})
        href = update_href_query_params(href, self.request.query_params)
        return OPDSLink(rel, href, MimeType.NAV)

    def _top_link(self, top_link):
        href = reverse("opds:v1:browser", kwargs={**top_link.kwargs, "page": 1})
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
                OPDSLink("search", reverse("opds:opensearch:1.1"), MimeType.OPENSEARCH),
            ]
            links += self._root_nav_links()
            if self.use_facets:
                for top_link in TopLinks.ALL + RootTopLinks.ALL:
                    if not self.is_top_link_displayed(top_link):
                        links += [self._top_link(top_link)]
                if facets := self._facets():
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
            query_params=top_link.query_params,
            summary=top_link.desc,
        )
        issue_max = self.obj.get("issue_max")
        data = (self.acquisition_groups, issue_max, False)
        return OPDS1Entry(entry_obj, {}, data)

    def _add_top_links(self, top_links):
        """Add a list of top links as entries if they should be enabled."""
        entries = []
        for tl in top_links:
            if not self.is_top_link_displayed(tl):
                entries += [self._top_link_entry(tl)]
        return entries

    def _get_entries_section(self, key, metadata):
        """Get entries by key section."""
        entries = []
        issue_max = self.obj.get("issue_max")
        data = (self.acquisition_groups, issue_max, metadata)
        if objs := self.obj.get(key):
            for obj in objs:
                entries += [OPDS1Entry(obj, self.request.query_params, data)]
        return entries

    @property
    def entries(self):
        """Create all the entries."""
        entries = []
        try:
            at_root = self.kwargs.get("pk") == 0
            if not self.use_facets and self.kwargs.get("page") == 1:
                entries += self._add_top_links(TopLinks.ALL)
                if at_root:
                    entries += self._add_top_links(RootTopLinks.ALL)
                entries += self._facets(entries=True, root=at_root)

            entries += self._get_entries_section("groups", False)
            metadata = (
                self.request.query_params.get("opdsMetadata", "").lower() not in FALSY
            )
            entries += self._get_entries_section("books", metadata)
        except Exception as exc:
            LOG.exception(exc)
        return entries

    def get_object(self):
        """Get the browser page and serialize it for this subclass."""
        group = self.kwargs.get("group")
        self.acquisition_groups = frozenset(self.valid_nav_groups[-2:])
        self.is_opds_1_acquisition = group in self.acquisition_groups
        self.is_opds_metadata = (
            self.request.query_params.get("opdsMetadata", "").lower() not in FALSY
        )
        self.obj = super().get_object()
        self.is_aq_feed = self.obj.get("model_group") == "c"
        return self

    def _detect_user_agent(self):
        # Hacks for clients that don't support facets
        user_agent = self.request.headers.get("User-Agent")
        self.use_facets = False
        self.skip_order_facets = False
        if not user_agent:
            return
        for prefix in UserAgents.FACET_SUPPORT:
            if user_agent.startswith(prefix):
                self.use_facets = True
                break
        for prefix in UserAgents.CLIENT_REORDERS:
            if user_agent.startswith(prefix):
                self.skip_order_facets = True
                break

    @extend_schema(request=BrowserView.input_serializer_class)
    def get(self, *args, **kwargs):
        """Get the feed."""
        self.parse_params()
        self.validate_settings()
        self._detect_user_agent()
        self.skip_order_facets |= self.kwargs.get("group") == "c"

        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data, content_type=self.content_type)

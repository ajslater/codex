"""OPDS browser."""

from datetime import datetime, timezone

from django.urls import reverse
from django.utils.http import urlencode
from drf_spectacular.utils import extend_schema
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response

from codex.serializers.opds_v1 import (
    OPDSAcquisitionEntrySerializer,
    OPDSEntrySerializer,
    OPDSTemplateSerializer,
)
from codex.settings.logging import get_logger
from codex.views.browser.browser import BrowserView
from codex.views.opds_v1.entry import OPDSEntry
from codex.views.opds_v1.util import (
    BLANK_TITLE,
    DEFAULT_FACETS,
    Facet,
    FacetGroups,
    MimeType,
    OPDSLink,
    OpdsNs,
    Rel,
    TopLinks,
    UserAgents,
    update_href_query_params,
)
from codex.views.template import CodexXMLTemplateView


LOG = get_logger(__name__)


class OPDSBrowserView(BrowserView, CodexXMLTemplateView):
    """The main opds browser."""

    authentication_classes = (SessionAuthentication, BasicAuthentication)
    template_name = "opds/index.xml"
    serializer_class = OPDSTemplateSerializer

    AQUISITION_GROUPS = set(("s", "f"))

    @property
    def opds_ns(self):
        """Dynamic opds namespace."""
        try:
            if self.is_aq_feed:
                ns = OpdsNs.ACQUISITION
            else:
                ns = OpdsNs.CATALOG
            return ns
        except Exception as exc:
            LOG.exception(exc)

    @property
    def id(self):
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
                names = []
                for name in (parent_name, group_name):
                    if name:
                        names.append(name)

                result = " ".join(names).strip()

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
                num_pages = self.obj.get("num_pages", 0)
                if num_pages > 1:
                    res = self.MAX_OBJ_PER_PAGE
                else:
                    res = len(self.obj.get("obj_list", []))
                return res
        except Exception as exc:
            LOG.exception(exc)

    @property
    def total_results(self):
        """Return opensearch:totalResults."""
        try:
            if self.params.get("q"):
                num_pages = self.obj.get("num_pages", 0)
                if num_pages > 1:
                    res = self.MAX_OBJ_PER_PAGE * num_pages
                else:
                    res = len(self.obj.get("obj_list", []))
                return res
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

        title = " ".join((facet_group.title_prefix, facet_title)).strip()
        link = OPDSLink(
            Rel.FACET,
            href,
            MimeType.NAV,
            title=title,
            facet_group=facet_group.query_param,
            facet_active=facet_active,
        )
        return link

    def _facet_entry(self, item, facet_group, facet, query_params):
        name = " ".join(
            (facet_group.glyph, facet_group.title_prefix, facet.title)
        ).strip()
        obj = {
            "group": item.get("group"),
            "pk": item.get("pk"),
            "name": name,
            "query_params": query_params,
        }
        return OPDSEntry(obj, self.valid_nav_groups, {**self.request.query_params})

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
            return

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
        if not entries:
            facet = self._facet(kwargs, facet_group, facet.title, qps)
        else:
            facet = self._facet_entry(kwargs, facet_group, facet, qps)
        return facet

    def _facet_group(self, facet_group, entries):
        facets = []
        for facet in facet_group.facets:
            if facet_obj := self._facet_or_facet_entry(facet_group, facet, entries):
                facets += [facet_obj]
        return facets

    def _facets(self, entries=False):
        facets = []
        if not self.skip_order_facets:
            facets += self._facet_group(FacetGroups.ORDER_BY, entries)
            facets += self._facet_group(FacetGroups.ORDER_REVERSE, entries)
        facets += self._facet_group(FacetGroups.TOP_GROUP, entries)
        if facet_obj := self._facet_or_facet_entry(
            FacetGroups.TOP_GROUP, Facet("f", "Folder View"), entries
        ):
            facets += [facet_obj]
        return facets

    def _nav_link(self, kwargs, rel):
        href = reverse("opds:v1:browser", kwargs={**kwargs, "page": 1})
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
        page = self.obj.get("page", 1)
        if page > 1:
            route = {**self.kwargs, "page": page - 1}
            links += [self._nav_link(route, Rel.PREV)]
        if page < self.obj.get("num_pages", 1):
            route = {**self.kwargs, "page": page + 1}
            links += [self._nav_link(route, Rel.NEXT)]
        return links

    def is_top_link_displayed(self, top_link):
        """Determine if this top link should be displayed."""
        is_displayed = True
        for key, val in top_link.kwargs.items():
            if key == "page":
                continue
            if self.kwargs.get(key) != val:
                is_displayed = False
                break
        if not is_displayed:
            for key, val in top_link.query_params.items():
                if self.request.query_params.get(key) != val:
                    is_displayed = False
                    break
        return is_displayed

    @property
    def links(self):
        """Create all the links."""
        links = []
        try:
            if self.is_aq_feed:
                mime_type = MimeType.ACQUISITION
            else:
                mime_type = MimeType.NAV
            links += [
                OPDSLink("self", self.request.get_full_path(), mime_type),
                OPDSLink(
                    Rel.AUTHENTICATION,
                    reverse("opds:v1:authentication"),
                    MimeType.AUTHENTICATION,
                ),
                OPDSLink("search", reverse("opds:v1:opensearch"), MimeType.OPENSEARCH),
            ]
            links += self._root_nav_links()
            if self.use_facets:
                for top_link in TopLinks.ALL:
                    links += [self._top_link(top_link)]
                if facets := self._facets():
                    links += facets
        except Exception as exc:
            LOG.exception(exc)
        return links

    def _top_link_entry(self, top_link):
        """Create a entry instead of a facet."""
        entry_obj = {
            **top_link.kwargs,
            "name": " ".join((top_link.glyph, top_link.title)),
            "query_params": top_link.query_params,
            "summary": top_link.desc,
        }

        return OPDSEntry(entry_obj, self.valid_nav_groups, {})

    @property
    def entries(self):
        """Create all the entries."""
        entries = []
        try:
            if not self.use_facets:
                for tl in TopLinks.ALL:
                    if not self.is_top_link_displayed(tl):
                        entries += [self._top_link_entry(tl)]
                entries += self._facets(entries=True)

            if obj_list := self.obj.get("obj_list"):
                at_top = self.kwargs.get("pk") == 0
                for entry_obj in obj_list:
                    entries += [
                        OPDSEntry(
                            entry_obj,
                            self.valid_nav_groups,
                            self.request.query_params,
                            at_top,
                        )
                    ]
        except Exception as exc:
            LOG.exception(exc)
        return entries

    def get_object(self):
        """Get the browser page and serialize it for this subclass."""
        group = self.kwargs.get("group")
        if group in self.AQUISITION_GROUPS:
            self.is_opds_acquisition = True
        browser_page = super().get_object()
        # this serialization fixes the unionfix prefixes
        obj_list = browser_page.get("obj_list")
        model_group = browser_page.get("model_group")
        if model_group == "c":
            serializer_class = OPDSAcquisitionEntrySerializer
        else:
            serializer_class = OPDSEntrySerializer
        serializer = serializer_class(obj_list, many=True)
        browser_page["obj_list"] = serializer.data
        self.obj = browser_page
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
    def get(self, request, *args, **kwargs):
        """Get the feed."""
        self.parse_params()
        self.validate_settings()
        self._detect_user_agent()

        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data, content_type=self.content_type)

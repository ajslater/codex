"""OPDS 1 feed."""
from datetime import datetime, timezone

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
)
from codex.views.opds.v1.const import (
    OpdsNs,
    RootTopLinks,
    TopLinks,
    UserAgents,
)
from codex.views.opds.v1.entry import OPDS1Entry
from codex.views.opds.v1.links import LinksMixin
from codex.views.template import CodexXMLTemplateView

LOG = get_logger(__name__)


class OPDS1FeedView(CodexXMLTemplateView, LinksMixin):
    """OPDS 1 Feed."""

    authentication_classes = (BasicAuthentication, SessionAuthentication)
    template_name = "opds_v1/index.xml"
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
                entries += self.add_top_links(TopLinks.ALL)
                if at_root:
                    entries += self.add_top_links(RootTopLinks.ALL)
                entries += self.facets(entries=True, root=at_root)

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
        # defaults in FacetsMixin
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

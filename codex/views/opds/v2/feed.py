"""OPDS v2.0 Feed."""

from datetime import datetime, timezone
from types import MappingProxyType

from drf_spectacular.utils import extend_schema
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import AdminFlag
from codex.serializers.opds.v2 import OPDS2FeedSerializer
from codex.views.browser.browser import BrowserView
from codex.views.const import FALSY
from codex.views.opds.const import BLANK_TITLE
from codex.views.opds.v2.const import (
    FACETS,
    FACETS_SECTION_DATA,
    GROUPS,
    GROUPS_SECTION_DATA,
    TOP_NAV_GROUP_SECTION_DATA,
    NavigationGroup,
)
from codex.views.opds.v2.links import HrefData, LinkData
from codex.views.opds.v2.publications import PublicationMixin
from codex.views.opds.v2.top_links import TopLinksMixin

LOG = get_logger(__name__)


class OPDS2FeedView(PublicationMixin, TopLinksMixin):
    """OPDS 2.0 Feed."""

    DEFAULT_ROUTE_NAME = "opds:v2:feed"

    authentication_classes = (BasicAuthentication, SessionAuthentication)
    serializer_class = OPDS2FeedSerializer

    def _title(self, browser_title):
        """Create the feed title."""
        result = ""
        if browser_title:
            parent_name = browser_title.get("parent_name", "All")
            if not parent_name and self.kwargs.get("pk") == 0:
                parent_name = "All"
            group_name = browser_title.get("group_name")
            result = " ".join(filter(None, (parent_name, group_name))).strip()

        if not result:
            result = BLANK_TITLE
        return result

    def _detect_user_agent(self):
        """Hacks for individual clients."""
        user_agent = self.request.headers.get("User-Agent")
        if not user_agent:
            return

    @staticmethod
    def _is_allowed(link_spec):
        """Return if the link allowed."""
        if (
            getattr(link_spec, "group", None) == "f"
            or getattr(link_spec, "query_param_value", None) == "f"
        ):
            # Folder perms
            efv_flag = (
                AdminFlag.objects.only("on")
                .get(key=AdminFlag.FlagChoices.FOLDER_VIEW.value)
                .on
            )
            if not efv_flag:
                return False
        return True

    @staticmethod
    def _create_link_kwargs(data, link_spec):
        """Create link kwargs."""
        if data.group_kwarg:
            # Nav Groups
            pk = getattr(link_spec, "pk", 0)
            kwargs = {"group": link_spec.group, "pk": pk, "page": 1}
        elif link_spec.query_param_value in ("f", "a"):
            # Special Facets
            kwargs = {
                "group": link_spec.query_param_value,
                "pk": 0,
                "page": 1,
            }
        else:
            # Regular Facets
            kwargs = None
        return kwargs

    @staticmethod
    def _create_link_query_params(group_spec, link_spec, kwargs):
        """Create link query params."""
        if qp_key := getattr(group_spec, "query_param_key", None):
            # Facet shorthand with group
            qps = {qp_key: link_spec.query_param_value}
        elif ls_qps := getattr(link_spec, "query_params", None):
            # Nav Group
            qps = ls_qps
        else:
            # Regular Group
            qps = None

        # Special order by for story_arcs
        if (
            kwargs
            and kwargs.get("group") == "a"
            and kwargs.get("pk")
            and (not qps or not qps.get("orderBy"))
        ):
            if not qps:
                qps = {}
            qps["orderBy"] = "story_arc_number"
        return qps

    def _create_links_section(self, group_specs, data):
        """Create links sections for groups and facets."""
        groups = []
        for group_spec in group_specs:
            link_dict = {}
            for link_spec in group_spec.links:
                if not self._is_allowed(link_spec):
                    continue

                kwargs = self._create_link_kwargs(data, link_spec)

                qps = self._create_link_query_params(group_spec, link_spec, kwargs)

                title = getattr(link_spec, "title", "")
                if not title:
                    title = getattr(link_spec, "name", "")

                href_data = HrefData(kwargs, qps)

                rel = data.rel if data.rel else link_spec.rel
                link_data = LinkData(rel, href_data, title=title)
                link = self.link(link_data)
                self.link_aggregate(link_dict, link)
            links = self.get_links_from_dict(link_dict)
            if links:
                metadata = {"title": group_spec.title}
                if data.subtitle:
                    metadata["subtitle"] = data.subtitle
                group = {
                    "metadata": metadata,
                    data.links_key: links,
                }
                groups.append(group)
        return groups

    def _get_groups(self, group_qs, book_qs, title, issue_number_max):
        groups = []

        # Top Nav Groups
        groups += self._create_links_section(GROUPS, TOP_NAV_GROUP_SECTION_DATA)

        # Regular Groups
        group_nav_dict = {"title": title, "links": group_qs}
        tup = (NavigationGroup(**group_nav_dict),)
        groups += self._create_links_section(tup, GROUPS_SECTION_DATA)

        # Publications
        groups += self.get_publications(book_qs, issue_number_max, title)

        return groups

    def _get_facets(self):
        return self._create_links_section(FACETS, FACETS_SECTION_DATA)

    def get_object(self):
        """Get the browser page and serialize it for this subclass."""
        group = self.kwargs.get("group")
        if group in ("f", "a"):
            self.acquisition_groups = frozenset()
        else:
            self.acquisition_groups = frozenset(self.valid_nav_groups[-2:])
        if group == "a":
            pk = self.kwargs["pk"]
            self.is_opds_2_acquisition = bool(pk)
        else:
            self.is_opds_2_acquisition = group in self.acquisition_groups
        self.is_opds_metadata = (
            self.request.query_params.get("opdsMetadata", "").lower() not in FALSY
        )
        browser_page = super().get_object()
        groups = browser_page.get("groups")
        books = browser_page.get("books")

        self.is_aq_feed = browser_page.get("model_group") == "c"

        ts: int = browser_page["covers_timestamp"]  # type: ignore
        datetime.fromtimestamp(ts, tz=timezone.utc)
        self.num_pages = browser_page["num_pages"]
        number_of_items = browser_page["total_count"]
        title = self._title(browser_page.get("browser_title"))
        return MappingProxyType(
            {
                "metadata": {
                    "title": title,
                    "number_of_items": number_of_items,
                    "items_per_page": self.MAX_OBJ_PER_PAGE,
                    "current_page": self.kwargs.get("page"),
                },
                "links": self.get_links(browser_page["up_route"]),
                "facets": self._get_facets(),
                "groups": self._get_groups(
                    groups, books, title, browser_page["issue_number_max"]
                ),
            }
        )

    @extend_schema(
        request=BrowserView.input_serializer_class,
        parameters=[BrowserView.input_serializer_class],
    )
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        self.parse_params()
        self.validate_settings()
        # self._detect_user_agent()

        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

"""OPDS v2.0 Feed."""

from types import MappingProxyType

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import AdminFlag
from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v2 import OPDS2FeedSerializer
from codex.views.const import MAX_OBJ_PER_PAGE
from codex.views.opds.auth import OPDSAuthMixin
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
from codex.views.opds.v2.publications import OPDS2PublicationView

LOG = get_logger(__name__)


class OPDS2FeedView(OPDSAuthMixin, OPDS2PublicationView):
    """OPDS 2.0 Feed."""

    DEFAULT_ROUTE = MappingProxyType(
        {**OPDS2PublicationView.DEFAULT_ROUTE, "name": "opds:v2:feed"}
    )
    TARGET = "opds2"
    throttle_scope = "opds"

    serializer_class = OPDS2FeedSerializer
    input_serializer_class = OPDSSettingsSerializer

    def _title(self, browser_title):
        """Create the feed title."""
        result = ""
        if browser_title:
            parent_name = browser_title.get("parent_name", "All")
            pks = self.kwargs["pks"]
            if not parent_name and not pks:
                parent_name = "All"
            group_name = browser_title.get("group_name")
            result = " ".join(filter(None, (parent_name, group_name))).strip()

        if not result:
            result = BLANK_TITLE
        return result

    # def _detect_user_agent(self):
    #    """Hacks for individual clients."""
    #    user_agent = self.request.headers.get("User-Agent")
    #    if not user_agent:
    #        return

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
            pks = getattr(link_spec, "ids", (0,))
            kwargs = {"group": link_spec.group, "pks": pks, "page": 1}
        elif link_spec.query_param_value in ("f", "a"):
            # Special Facets
            kwargs = {
                "group": link_spec.query_param_value,
                "pks": (0,),
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
            and kwargs.get("pks")
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

    def _get_groups(self, group_qs, book_qs, title, zero_pad):
        groups = []

        # Top Nav Groups
        groups += self._create_links_section(GROUPS, TOP_NAV_GROUP_SECTION_DATA)

        # Regular Groups
        group_nav_dict = {"title": title, "links": group_qs}
        tup = (NavigationGroup(**group_nav_dict),)
        groups += self._create_links_section(tup, GROUPS_SECTION_DATA)

        # Publications
        groups += self.get_publications(book_qs, zero_pad, title)

        return groups

    def _get_facets(self):
        return self._create_links_section(FACETS, FACETS_SECTION_DATA)

    def get_object(self):
        """Get the browser page and serialize it for this subclass."""
        group_qs, book_qs, _, total_count, zero_pad, mtime = self.group_and_books
        title = self.get_browser_page_title()
        # convert browser_page into opds page

        # opds page
        title = self._title(title)
        number_of_items = total_count
        current_page = self.kwargs.get("page")
        up_route = self.get_last_route()
        links = self.get_links(up_route)
        facets = self._get_facets()

        # opds groups
        page_groups = group_qs
        page_books = book_qs
        groups = self._get_groups(page_groups, page_books, title, zero_pad)

        return MappingProxyType(
            {
                "metadata": {
                    "title": title,
                    "modified": mtime,
                    "number_of_items": number_of_items,
                    "items_per_page": MAX_OBJ_PER_PAGE,
                    "current_page": current_page,
                },
                "links": links,
                "facets": facets,
                "groups": groups,
            }
        )

    @extend_schema(
        parameters=[input_serializer_class],
    )
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

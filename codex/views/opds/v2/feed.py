"""OPDS v2.0 Feed."""

from copy import copy
from types import MappingProxyType
from typing import TYPE_CHECKING

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v2.feed import OPDS2FeedSerializer
from codex.settings import MAX_OBJ_PER_PAGE
from codex.views.mixins import UserActiveMixin
from codex.views.opds.const import BLANK_TITLE
from codex.views.opds.v2.const import (
    FACETS,
    FACETS_SECTION_DATA,
    GROUPS_SECTION_DATA,
    ORDERED_GROUPS,
    START_GROUPS,
    START_SECTION_DATA,
    TOP_GROUPS,
    TOP_NAV_GROUP_SECTION_DATA,
    NavigationGroup,
)
from codex.views.opds.v2.href import HrefData
from codex.views.opds.v2.links import LinkData
from codex.views.opds.v2.publications import OPDS2PublicationsView

if TYPE_CHECKING:
    from collections.abc import Mapping


class OPDS2FeedView(UserActiveMixin, OPDS2PublicationsView):
    """OPDS 2.0 Feed."""

    TARGET: str = "opds2"
    throttle_scope = "opds"

    serializer_class: type[BaseSerializer] | None = OPDS2FeedSerializer
    input_serializer_class: type[OPDSSettingsSerializer] = OPDSSettingsSerializer  # pyright: ignore[reportIncompatibleVariableOverride]

    def _title(self, browser_title):
        """Create the feed title."""
        result = ""
        if browser_title:
            parent_name = browser_title.get("parent_name", None)
            pks = self.kwargs["pks"]
            if not parent_name and not pks:
                parent_name = "All"
            group_name = browser_title.get("group_name")
            result = " ".join(filter(None, (parent_name, group_name))).strip()

        if not result:
            result = BLANK_TITLE
        return result

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
                .get(key=AdminFlagChoices.FOLDER_VIEW.value)
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

    def _create_links_section_link_spec(self, link_spec, data, group_spec, link_dict):
        if not self._is_allowed(link_spec):
            return

        kwargs = self._create_link_kwargs(data, link_spec)

        qps = self._create_link_query_params(group_spec, link_spec, kwargs)

        title = getattr(link_spec, "title", "")
        if not title:
            title = getattr(link_spec, "name", "")
        if not title and data.links_key == "navigation":
            title = self.EMPTY_TITLE

        href_data = HrefData(kwargs, qps)

        rel = data.rel if data.rel else link_spec.rel
        link_data = LinkData(rel, href_data, title=title)
        link = self.link(link_data)
        self.link_aggregate(link_dict, link)

    def _create_links_section_group_spec(
        self, group_spec, data, groups, *, paginate: bool = False
    ):
        link_dict = {}
        for link_spec in group_spec.links:
            self._create_links_section_link_spec(link_spec, data, group_spec, link_dict)
        links = self.get_links_from_dict(link_dict)
        if links:
            metadata = {"title": group_spec.title}
            if data.subtitle:
                metadata["subtitle"] = data.subtitle

            current_page = self.kwargs.get("page", 1)
            if paginate:
                pagination = {
                    "current_page": current_page,
                    "items_per_page": MAX_OBJ_PER_PAGE,
                    "number_of_items": self._opds_number_of_groups,
                }
                metadata.update(pagination)
            group: dict[str, Mapping | list] = {
                "metadata": metadata,
            }
            if data.add_self_link:
                group["links"] = [self.link_self()]
            group[data.links_key] = links
            groups.append(group)

    def _create_links_section(self, group_specs, data, *, paginate: bool = False):
        """Create links sections for groups and facets."""
        groups = []
        for group_spec in group_specs:
            self._create_links_section_group_spec(
                group_spec, data, groups, paginate=paginate
            )
        return groups

    def _get_top_groups(self):
        # Top Nav Groups
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        if group in {"r", "f", "a"} and (not pks or 0 in pks):
            return self._create_links_section(TOP_GROUPS, TOP_NAV_GROUP_SECTION_DATA)
        return []

    def _get_ordered_groups(self):
        # Top Nav Groups
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        if group in {"r", "f", "a"} and (not pks or 0 in pks):
            return self._create_links_section(
                ORDERED_GROUPS, TOP_NAV_GROUP_SECTION_DATA
            )

        return []

    def _get_start_groups(self):
        # Top Nav Groups
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        if group in {"r", "f", "a"} and (not pks or 0 in pks):
            return []
        return self._create_links_section(START_GROUPS, START_SECTION_DATA)

    def _get_groups(self, group_qs, book_qs, title, zero_pad):
        groups = []

        # Regular Groups
        tup = (NavigationGroup(title=title, links=group_qs),)
        groups_section_data = copy(GROUPS_SECTION_DATA)
        subtitle = group_qs.model.__name__ if group_qs.model else "UnknownGroup"
        if subtitle != "Series":
            subtitle += "s"
        groups_section_data.subtitle = subtitle
        groups += self._create_links_section(tup, groups_section_data, paginate=True)

        # Publications
        groups += self.get_publications(book_qs, zero_pad, title)

        return groups

    def _get_facets(self):
        return self._create_links_section(FACETS, FACETS_SECTION_DATA)

    @override
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

        # Called "Browse"" in Stump
        regular_groups = self._get_groups(group_qs, book_qs, title, zero_pad)
        first_regular_groups = next(iter(regular_groups), {})
        navigation = first_regular_groups.pop("navigation", [])

        # opds groups
        groups = []
        groups += regular_groups
        groups += self._get_ordered_groups()
        groups += self._get_top_groups()
        groups += self._get_facets()
        groups += self._get_start_groups()

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
                "navigation": navigation,
                "groups": groups,
            }
        )

    @override
    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        self.mark_user_active()
        return Response(serializer.data)

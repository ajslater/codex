"""OPDS v2.0 Feed."""

from collections.abc import Mapping
from copy import copy
from types import MappingProxyType

from caseconverter import snakecase
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.models.groups import BrowserGroupModel, Folder
from codex.models.named import StoryArc
from codex.serializers.browser.settings import OPDSSettingsSerializer
from codex.serializers.opds.v2.feed import OPDS2FeedSerializer
from codex.settings import MAX_OBJ_PER_PAGE
from codex.views.browser.browser import BrowserView
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
    Link,
    LinkGroup,
    LinksSectionData,
)
from codex.views.opds.v2.href import HrefData
from codex.views.opds.v2.links import LinkData
from codex.views.opds.v2.publications import OPDS2PublicationsView

PUBLICATION_PREVIEW_LIMIT = 5
_START_GROUPS = frozenset({"r", "f", "a"})


class OPDS2FeedView(UserActiveMixin, OPDS2PublicationsView):
    """OPDS 2.0 Feed."""

    TARGET: str = "opds2"
    throttle_scope = "opds"

    serializer_class: type[BaseSerializer] | None = OPDS2FeedSerializer
    input_serializer_class: type[OPDSSettingsSerializer] = OPDSSettingsSerializer  # pyright: ignore[reportIncompatibleVariableOverride]

    def _title(self, browser_title):
        """Create the feed title."""
        result = self.request.GET.get("title", "")
        if not result and browser_title:
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
    def _is_allowed(link_spec: Link | BrowserGroupModel):
        """Return if the link allowed."""
        if (
            isinstance(link_spec, Link)
            and (
                link_spec.group == "f"
                or (
                    link_spec.query_params
                    and link_spec.query_params.get("topGroup") == "f"
                )
            )
        ) or isinstance(link_spec, Folder):
            # Folder perms
            efv_flag = (
                AdminFlag.objects.only("on")
                .get(key=AdminFlagChoices.FOLDER_VIEW.value)
                .on
            )
            if not efv_flag:
                return False
        return True

    def _create_link_kwargs(self, link_spec: Link | BrowserGroupModel):
        """Create link kwargs."""
        if isinstance(link_spec, Link):
            group = (
                link_spec.group if link_spec.group else self.kwargs.get("group", "r")
            )
            pks = (0,)
        else:
            group = link_spec.__class__.__name__[0].lower()
            pks = link_spec.ids  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        return {"group": group, "pks": pks, "page": 1}

    @staticmethod
    def _create_link_query_params(link_spec: Link | BrowserGroupModel, kwargs: Mapping):
        """Create link query params."""
        if not isinstance(link_spec, Link | StoryArc):
            return {}
        qps = link_spec.query_params if isinstance(link_spec, Link) else {}

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

    def _create_publications_preview(
        self, link_spec: Link | BrowserGroupModel, group_spec: LinkGroup
    ):
        browser_view = BrowserView()
        browser_view.request = self.request
        group = (
            link_spec.group
            if isinstance(link_spec, Link)
            else link_spec.__class__.__name__[0].lower()
        )
        browser_view.kwargs = {"group": group, "pks": [0], "page": 1}
        params = {}
        if isinstance(link_spec, Link) and link_spec.query_params:
            for key, value in link_spec.query_params.items():
                params[snakecase(key)] = value
        params["show"] = {"p": True, "s": True}
        params["limit"] = PUBLICATION_PREVIEW_LIMIT

        browser_view.set_params(params)
        book_qs, book_count, zero_pad = browser_view.get_book_qs()
        if not book_count:
            return []

        link_spec = next(iter(group_spec.links))
        return self.get_publications(
            book_qs,
            zero_pad,
            group_spec.title,
            "",
            PUBLICATION_PREVIEW_LIMIT,
            link_spec,
            number_of_items=book_count,
        )

    def _create_links_section_link_spec(
        self,
        link_spec: Link,
        data: LinksSectionData,
        link_dict: Mapping,
    ):
        if not self._is_allowed(link_spec):
            return

        kwargs = self._create_link_kwargs(link_spec)

        qps = self._create_link_query_params(link_spec, kwargs)

        title = getattr(link_spec, "title", "")
        if not title:
            title = getattr(link_spec, "name", "")
        if not title:
            title = self.EMPTY_TITLE

        href_data = HrefData(kwargs, qps, inherit_query_params=True)

        rel = data.rel if data.rel else link_spec.rel
        link_data = LinkData(rel, href_data, title=title)
        link = self.link(link_data)
        self.link_aggregate(link_dict, link)

    def _create_links_section_group_spec(
        self, group_spec: LinkGroup, data: LinksSectionData, *, paginate: bool = False
    ):
        groups = []
        link_dict = {}
        for link_spec in group_spec.links:
            self._create_links_section_link_spec(link_spec, data, link_dict)
        links = self.get_links_from_dict(link_dict)
        if links:
            metadata: dict[str, str | int] = {"title": group_spec.title}
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
            group["navigation"] = links
            groups += [group]

        return groups

    def _create_links_section(self, group_specs, data, *, paginate: bool = False):
        """Create links sections for groups and facets."""
        groups = []
        for group_spec in group_specs:
            groups += self._create_links_section_group_spec(
                group_spec, data, paginate=paginate
            )
        return groups

    @property
    def is_start_page(self):
        """Memoize if we're on the start page."""
        if self._is_start_page is None:
            group = self.kwargs.get("group")
            pks = self.kwargs.get("pks")
            self._is_start_page = (
                group in _START_GROUPS
                and (not pks or 0 in pks)
                and not self.request.GET.get("filters")
            )

        return self._is_start_page

    def _get_top_groups(self):
        """Top Nav Groups."""
        groups = []
        if self.is_start_page:
            groups += self._create_links_section(TOP_GROUPS, TOP_NAV_GROUP_SECTION_DATA)
        return groups

    def _get_ordered_groups(self):
        # Top Nav Groups
        groups = []
        if self.is_start_page:
            for group_spec in ORDERED_GROUPS:
                # explode into individual groups
                for link_spec in group_spec.links:
                    group_spec.title = link_spec.title
                    pub_section = self._create_publications_preview(
                        link_spec, group_spec
                    )
                    groups += pub_section
        return groups

    def _get_start_groups(self):
        # Top Nav Groups
        if self.is_start_page:
            return []
        return self._create_links_section(START_GROUPS, START_SECTION_DATA)

    def _get_groups(self, group_qs, book_qs, title: str, zero_pad: int):
        groups = []

        # Regular Groups
        tup = (LinkGroup(title, group_qs),)
        groups_section_data = copy(GROUPS_SECTION_DATA)
        subtitle = group_qs.model.__name__ if group_qs.model else "UnknownGroup"
        if subtitle != "Series":
            subtitle += "s"
        groups_section_data.subtitle = subtitle
        groups += self._create_links_section(tup, groups_section_data, paginate=True)

        # Publications
        groups += self.get_publications(book_qs, zero_pad, title, subtitle=subtitle)

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
        zero_pad = zero_pad if zero_pad else 0

        # Move the first group's navigation to become the feed navigation.
        # The feed navigation is titled "Browse"" in Stump
        regular_groups = self._get_groups(group_qs, book_qs, title, zero_pad)
        first_regular_group = next(iter(regular_groups), {})
        navigation = first_regular_group.pop("navigation", [])

        # opds groups
        groups = []
        if first_regular_group.get("publications"):
            groups += regular_groups
        og = self._get_ordered_groups()
        groups += og
        groups += self._get_top_groups()
        groups += self._get_facets()
        groups += self._get_start_groups()

        number_of_items = total_count
        current_page = self.kwargs.get("page")
        up_route = self.get_last_route()
        links = self.get_links(up_route)

        feed = {
            "metadata": {
                "title": title,
                "modified": mtime,
                "number_of_items": number_of_items,
                "items_per_page": MAX_OBJ_PER_PAGE,
                "current_page": current_page,
            },
            "links": links,
        }
        if navigation:
            feed["navigation"] = navigation
        if groups:
            feed["groups"] = groups

        return MappingProxyType(feed)

    @override
    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs):
        """Get the feed."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        self.mark_user_active()
        return Response(serializer.data)

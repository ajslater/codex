"""OPDS v2.0 Feed Groups."""

from collections.abc import Mapping

from codex.models.groups import BrowserGroupModel
from codex.models.named import StoryArc
from codex.settings import MAX_OBJ_PER_PAGE
from codex.views.opds.const import BLANK_TITLE, Rel
from codex.views.opds.v2.const import (
    FACETS,
    PREVIEW_GROUPS,
    START_GROUPS,
    TOP_GROUPS,
    HrefData,
    Link,
    LinkData,
    LinkGroup,
)
from codex.views.opds.v2.feed.publications import OPDS2PublicationsView


class OPDS2FeedGroupsView(OPDS2PublicationsView):
    """OPDS 2.0 Feed Groups."""

    #########
    # Links #
    #########

    def _create_link_kwargs(self, link_spec: Link | BrowserGroupModel):
        """Create link kwargs."""
        if isinstance(link_spec, Link):
            if link_spec.group is None:
                # Start Link
                return {}
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
            qps = dict(qps) if qps else {}
            qps["orderBy"] = "story_arc_number"
        return qps

    def _create_links_from_link_spec(
        self,
        link_spec: Link | BrowserGroupModel,
        link_dict: Mapping,
    ):
        if not self.is_allowed(link_spec):
            return

        kwargs = self._create_link_kwargs(link_spec)
        qps = self._create_link_query_params(link_spec, kwargs)

        title = getattr(link_spec, "title", "")
        if not title:
            title = getattr(link_spec, "name", "")
        if not title:
            title = BLANK_TITLE

        if isinstance(link_spec, Link):
            inherit_query_params = link_spec.inherit_query_params
            rel = link_spec.rel
        else:
            inherit_query_params = True
            rel = Rel.SUB

        url_name = "opds:v2:start" if not kwargs else None
        href_data = HrefData(
            kwargs, qps, url_name=url_name, inherit_query_params=inherit_query_params
        )

        link_data = LinkData(rel, href_data, title=title)
        link = self.link(link_data)
        self.link_aggregate(link_dict, link)

    ##########
    # Groups #
    ##########

    def _create_group_from_group_spec(
        self, group_spec: LinkGroup, *, paginate: bool = False
    ):
        groups = []
        link_dict = {}
        for link_spec in group_spec.links:
            self._create_links_from_link_spec(link_spec, link_dict)
        links = self.get_links_from_dict(link_dict)
        if links:
            metadata: dict[str, str | int] = {"title": group_spec.title}
            if group_spec.subtitle:
                metadata["subtitle"] = group_spec.subtitle

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

    def _create_group(self, group_specs, *, paginate: bool = False):
        """Create links sections for groups and facets."""
        groups = []
        for group_spec in group_specs:
            groups += self._create_group_from_group_spec(group_spec, paginate=paginate)
        return groups

    def _get_top_groups(self):
        """Top Nav Groups."""
        return self._create_group(TOP_GROUPS)

    def _get_ordered_groups(self):
        # Top Nav Groups
        groups = []
        for group_spec in PREVIEW_GROUPS:
            # explode into individual groups
            for link_spec in group_spec.links:
                pub_section = self.get_publications_preview(link_spec)
                groups += pub_section
        return groups

    def _get_start_groups(self):
        # Top Nav Groups
        return self._create_group(START_GROUPS)

    def _get_groups(self, group_qs, book_qs, title: str, zero_pad: int):
        groups = []

        # Regular Groups
        tup = (LinkGroup(title, group_qs),)
        subtitle = group_qs.model.__name__ if group_qs.model else "UnknownGroup"
        if subtitle != "Series":
            subtitle += "s"
        groups += self._create_group(tup, paginate=True)

        # Publications
        groups += self.get_publications(book_qs, zero_pad, title, subtitle=subtitle)

        return groups

    def _get_facets(self):
        return self._create_group(FACETS)

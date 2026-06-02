"""OPDS v2 consts."""
# https://drafts.opds.io/opds-2.0.html

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from django.db.models.query import QuerySet

from codex.views.opds.const import BookmarkFilters, FavoriteFilters, Rel


@dataclass
class HrefData:
    """Data for creating hrefs."""

    kwargs: Mapping[str, str | Sequence[int] | int] | None = None
    query_params: Mapping[str, str | int | Mapping] | None = None
    inherit_query_params: bool = False
    url_name: str | None = None
    min_page: int | None = None
    max_page: int | None = None
    template: str = ""


@dataclass
class LinkData:
    """Data for creating links."""

    rel: str
    href_data: HrefData
    title: str | None = None
    mime_type: str | None = None
    template: str | None = None
    height: int | None = None
    width: int | None = None
    size: int | None = None
    href: str | None = None
    num_items: int | None = None
    authenticate: Mapping | None = None


@dataclass
class Link:
    """Groups Navigation Link."""

    rel: str
    title: str
    group: str | None = ""
    query_params: Mapping | None = None
    inherit_query_params: bool = True
    subtitle: str = ""


@dataclass
class LinkGroup:
    """Navigation Group."""

    title: str
    links: Sequence[Link] | QuerySet
    subtitle: str = ""


TOP_GROUPS = (
    LinkGroup(
        "Top Collections",
        (
            Link(Rel.SUB, "Publishers", "root", {"topCollection": "publishers"}),
            Link(Rel.SUB, "Series", "root", {"topCollection": "series"}),
            Link(Rel.SUB, "Issues", "root", {"topCollection": "comics"}),
            Link(Rel.SUB, "Folders", "folders", {"topCollection": "folders"}),
            Link(Rel.SUB, "Story Arcs", "arcs", {"topCollection": "arcs"}),
        ),
    ),
)

START_GROUPS = (
    LinkGroup(
        "Start (Reset filters & order)",
        (
            Link(
                Rel.START,
                "Start",
                None,
                {},
                inherit_query_params=False,
            ),
        ),
    ),
)
FACETS = (
    LinkGroup(
        "⏿ Read Filter",
        (
            Link(Rel.FACET, "Unread", "", {"filters": BookmarkFilters.UNREAD}),
            Link(
                Rel.FACET, "In Progress", "", {"filters": BookmarkFilters.IN_PROGRESS}
            ),
            Link(Rel.FACET, "Read", "", {"filters": BookmarkFilters.READ}),
            Link(Rel.FACET, "All", "", {"filters": BookmarkFilters.NONE}),
        ),
    ),
    LinkGroup(
        "⬄ Order By",
        (
            Link(Rel.FACET, "Date", "", {"orderBy": "date"}),
            Link(Rel.FACET, "Name", "", {"orderBy": "sort_name"}),
            Link(Rel.FACET, "Filename", "", {"orderBy": "filename"}),
        ),
    ),
    LinkGroup(
        "⇕ Order Direction",
        (
            Link(Rel.FACET, "Ascending", "", {"orderReverse": False}),
            Link(Rel.FACET, "Descending", "", {"orderReverse": True}),
        ),
    ),
)
_PREVIEW_GROUP_PARAMS = MappingProxyType(
    {
        "filters": BookmarkFilters.UNREAD,
    }
)
PREVIEW_GROUPS = (
    LinkGroup(
        "Ordered Groups",
        (
            Link(
                Rel.FEATURED,
                "Keep Reading",
                "root",
                MappingProxyType(
                    {
                        "topCollection": "comics",
                        **_PREVIEW_GROUP_PARAMS,
                        "orderBy": "bookmark_updated_at",
                        "orderReverse": True,
                        "title": "Keep Reading",
                    }
                ),
            ),
            Link(
                Rel.SORT_NEW,
                "Latest Unread",
                "root",
                MappingProxyType(
                    {
                        "topCollection": "comics",
                        **_PREVIEW_GROUP_PARAMS,
                        "orderBy": "created_at",
                        "orderReverse": True,
                        "title": "Latest Unread",
                    }
                ),
            ),
            Link(
                Rel.SORT_NEW,
                "Oldest Unread",
                "root",
                MappingProxyType(
                    {
                        "topCollection": "comics",
                        **_PREVIEW_GROUP_PARAMS,
                        "orderBy": "date",
                        "orderReverse": False,
                        "title": "Oldest Unread",
                    }
                ),
            ),
        ),
    ),
)

# Conditionally appended to PREVIEW_GROUPS on the start page when the
# requesting user has at least one favorite. Stays out of the static
# tuple so a fresh user doesn't see an always-empty "Favorites"
# section in their start feed. Inclusion is decided in
# ``OPDS2FeedGroupsView.get_ordered_groups`` per request.
FAVORITES_PREVIEW_GROUP = LinkGroup(
    "Favorites",
    (
        Link(
            Rel.FEATURED,
            "Favorites",
            "root",
            MappingProxyType(
                {
                    "topCollection": "comics",
                    "filters": FavoriteFilters.ONLY,
                    "orderBy": "sort_name",
                    "orderReverse": False,
                    "title": "Favorites",
                }
            ),
        ),
    ),
)

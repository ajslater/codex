"""OPDS v2 consts."""
# https://drafts.opds.io/opds-2.0.html

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from django.db.models.query import QuerySet

from codex.views.opds.const import BookmarkFilters, Rel


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
        "Top Groups",
        (
            Link(Rel.SUB, "Publishers", "r", {"topGroup": "p"}),
            Link(Rel.SUB, "Series", "p", {"topGroup": "p"}),
            Link(Rel.SUB, "Issues", "s", {"topGroup": "s"}),
            Link(Rel.SUB, "Folders", "f", {"topGroup": "f"}),
            Link(Rel.SUB, "Story Arcs", "a", {"topGroup": "a"}),
        ),
    ),
)
START_GROUPS = (
    LinkGroup(
        "Start",
        (Link(Rel.START, "Start", None, {}, inherit_query_params=False),),
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
        "topGroup": "s",
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
                "s",
                MappingProxyType(
                    {
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
                "s",
                MappingProxyType(
                    {
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
                "s",
                MappingProxyType(
                    {
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

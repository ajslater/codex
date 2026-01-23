"""OPDS v2 consts."""
# https://drafts.opds.io/opds-2.0.html

from collections.abc import Sequence
from dataclasses import dataclass

from django.db.models.query import QuerySet

from codex.settings import MAX_OBJ_PER_PAGE
from codex.views.opds.const import BookmarkFilters, Rel


@dataclass
class Link:
    """Groups Navigation Link."""

    rel: str
    title: str
    group: str | None = ""
    query_params: dict | None = None
    inherit_query_params: bool = True


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
PREVIEW_GROUPS = (
    LinkGroup(
        "Ordered Groups",
        (
            Link(
                Rel.FEATURED,
                "Keep Reading",
                "s",
                {
                    "topGroup": "s",
                    "filters": BookmarkFilters.UNREAD,
                    "orderBy": "bookmark_updated_at",
                    "orderReverse": True,
                    "limit": MAX_OBJ_PER_PAGE,
                    "title": "Keep Reading",
                },
            ),
            Link(
                Rel.SORT_NEW,
                "Latest Unread",
                "s",
                {
                    "topGroup": "s",
                    "filters": BookmarkFilters.UNREAD,
                    "orderBy": "created_at",
                    "orderReverse": True,
                    "limit": MAX_OBJ_PER_PAGE,
                    "title": "Latest Unread",
                },
            ),
            Link(
                Rel.SORT_NEW,
                "Oldest Unread",
                "s",
                {
                    "topGroup": "s",
                    "filters": BookmarkFilters.UNREAD,
                    "orderBy": "date",
                    "orderReverse": False,
                    "limit": MAX_OBJ_PER_PAGE,
                    "title": "Oldest Unread",
                },
            ),
        ),
    ),
)

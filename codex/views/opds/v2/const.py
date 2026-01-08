"""OPDS v2 consts."""

from dataclasses import dataclass

from codex.views.opds.const import Rel


@dataclass
class Facet:
    """OPDS Facet."""

    query_param_value: str | bool
    title: str


@dataclass
class FacetGroup:
    """opds:facetGroup."""

    title: str
    query_param_key: str
    glyph: str
    links: tuple[Facet, ...]


FACETS = (
    FacetGroup(
        "➠ Order By",
        "orderBy",
        "➠",
        (Facet("date", "Date"), Facet("sort_name", "Name")),
    ),
    FacetGroup(
        "⇕ Order Direction",
        "orderReverse",
        "⇕",
        (
            Facet(query_param_value=False, title="Ascending"),
            Facet(query_param_value=True, title="Descending"),
        ),
    ),
    FacetGroup(
        "⊙ Top Group",
        "topGroup",
        "⊙",
        (
            Facet("p", "Publishers View"),
            Facet("s", "Series View"),
            Facet("f", "Folder View"),
            Facet("a", "Story Arc View"),
        ),
    ),
    # Could add Filters as well.
)


@dataclass
class NavigationLink:
    """Groups Navigation Link."""

    rel: str
    title: str
    group: str
    query_params: dict | None


@dataclass
class NavigationGroup:
    """Navigation Group."""

    title: str
    links: tuple[NavigationLink, ...]


ORDERED_GROUPS = (
    NavigationGroup(
        "Ordered Groups",
        (
            NavigationLink(
                Rel.SORT_NEW,
                "New",
                "s",
                {"orderBy": "created_at", "orderReverse": True},
            ),
            NavigationLink(
                Rel.FEATURED,
                "Oldest Unread",
                "s",
                {"orderBy": "date", "orderReverse": False},
            ),
            NavigationLink(
                Rel.POPULAR,
                "Last Read",
                "s",
                {"orderBy": "bookmark_updated_at", "orderReverse": True},
            ),
        ),
    ),
)
TOP_GROUPS = (
    NavigationGroup(
        "Top Groups",
        (
            NavigationLink(Rel.START, "Publishers", "r", {"topGroup": "p"}),
            NavigationLink(Rel.SUB, "Series", "p", {"topGroup": "p"}),
            NavigationLink(Rel.SUB, "Issues", "s", {"topGroup": "p"}),
            NavigationLink(Rel.SUB, "Folders", "f", {"topGroup": "f"}),
            NavigationLink(Rel.SUB, "Story Arcs", "a", {"topGroup": "a"}),
        ),
    ),
)

START_GROUPS = (
    NavigationGroup(
        "Start",
        (
            NavigationLink(
                Rel.START,
                "Start",
                "r",
                {"topGroup": "p", "orderBy": "sort_name", "orderReverse": False},
            ),
        ),
    ),
)


@dataclass
class LinksSectionData:
    """Data for the create_links_section method."""

    subtitle: str | None = None
    rel: str | None = None
    group_kwarg: bool = False
    links_key: str = "navigation"
    add_self_link: bool = False


START_SECTION_DATA = LinksSectionData(rel=Rel.START, group_kwarg=True)
TOP_NAV_GROUP_SECTION_DATA = LinksSectionData(group_kwarg=True)
GROUPS_SECTION_DATA = LinksSectionData(
    rel=Rel.SUB,
    group_kwarg=True,
)
FACETS_SECTION_DATA = LinksSectionData(rel=Rel.FACET)

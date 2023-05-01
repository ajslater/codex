"""OPDS 1 Utility classes."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union

from comicbox.metadata.comic_json import json

from codex.views.opds.const import MimeType, Rel


class OpdsNs:
    """xml namespaces."""

    CATALOG = "http://opds-spec.org/2010/catalog"
    ACQUISITION = "http://opds-spec.org/2010/acquisition"


class UserAgents:
    """Control whether to hack in facets with nav links."""

    CLIENT_REORDERS = ("Chunky",)
    FACET_SUPPORT = ("yar",)  # kybooks
    # NO_FACET_SUPPORT "Panels", "Chunky", "PocketBook"


class TopRoutes:
    """Routes for top groups."""

    PUBLISHER = {"group": "p", "pk": 0}
    SERIES = {"group": "s", "pk": 0}
    FOLDER = {"group": "f", "pk": 0}
    ROOT = {"group": "r", "pk": 0}


@dataclass
class FacetGroup:
    """An opds:facetGroup."""

    title_prefix: str
    query_param: str
    glyph: str
    facets: tuple


@dataclass
class Facet:
    """An OPDS facet."""

    value: str
    title: str


@dataclass
class TopLink:
    """A non standard root link when facets are unsupported."""

    kwargs: dict
    rel: str
    mime_type: str
    query_params: defaultdict[str, Union[str, bool, int]]
    glyph: str
    title: str
    desc: str


class TopLinks:
    """Top link definitions."""

    START = TopLink(
        TopRoutes.ROOT,
        Rel.START,
        MimeType.NAV,
        defaultdict(),
        "⌂",
        "Start of the catalog",
        "",
    )
    ALL = (START,)


class RootTopLinks:
    """Top Links that only appear at the root."""

    NEW = TopLink(
        TopRoutes.SERIES,
        Rel.SORT_NEW,
        MimeType.ACQUISITION,
        defaultdict(
            None, {"orderBy": "created_at", "orderReverse": True, "limit": 100}
        ),
        "📥",
        "Recently Added",
        "",
    )
    FEATURED = TopLink(
        TopRoutes.SERIES,
        Rel.FEATURED,
        MimeType.NAV,
        defaultdict(
            None,
            {
                "orderBy": "date",
                "filters": json.dumps({"bookmark": "UNREAD"}),
                "limit": 100,
            },
        ),
        "📚",
        "Oldest Unread",
        "Unread issues, oldest published first",
    )
    LAST_READ = TopLink(
        TopRoutes.SERIES,
        Rel.POPULAR,
        MimeType.NAV,
        defaultdict(
            None, {"orderBy": "bookmark_updated_at", "orderReverse": True, "limit": 100}
        ),
        "👀",
        "Last Read",
        "Last Read issues, recently read first.",
    )
    ALL = (NEW, FEATURED, LAST_READ)


class FacetGroups:
    """Facet Group definitions."""

    ORDER_BY = FacetGroup(
        "Order By",
        "orderBy",
        "➠",
        (
            Facet("date", "Date"),
            Facet("sort_name", "Name"),
        ),
    )
    ORDER_REVERSE = FacetGroup(
        "Order",
        "orderReverse",
        "⇕",
        (Facet("false", "Ascending"), Facet("true", "Descending")),
    )
    ALL = (ORDER_BY, ORDER_REVERSE)


class RootFacetGroups:
    """Facet Groups that only appear at the root."""

    TOP_GROUP = FacetGroup(
        "",
        "topGroup",
        "⊙",
        (Facet("p", "Publishers View"), Facet("s", "Series View")),
    )
    ALL = (TOP_GROUP,)


DEFAULT_FACETS = {
    "topGroup": "p",
    "orderBy": "sort_name",
    "orderReverse": "false",
}


@dataclass
class OPDSLink:
    """An OPDS Link."""

    rel: str
    href: str
    mime_type: str
    title: str = ""
    length: int = 0
    facet_group: str = ""
    facet_active: bool = False
    thr_count: int = 0
    pse_count: int = 0
    pse_last_read: int = 0
    pse_last_read_date: Optional[datetime] = None

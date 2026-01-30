"""OPDS v1 const and data classes."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from codex.views.opds.const import MimeType, Rel, TopRoutes

DEFAULT_FACETS = MappingProxyType(
    {
        "topGroup": "p",
        "orderBy": "sort_name",
        "orderReverse": "false",
    }
)


@dataclass
class TopLink:
    """A non standard root link when facets are unsupported."""

    kwargs: Mapping
    rel: str
    mime_type: str
    query_params: Mapping[str, str | bool | int]
    glyph: str
    title: str
    desc: str
    url_name: str = "opds:v1:feed"


class TopLinks:
    """Top link definitions."""

    START = TopLink(
        {},  # TopRoutes.ROOT,
        Rel.START,
        MimeType.NAV,
        {},  # {"topGroup": "p"},
        "⌂",
        "Start of catalog",
        "",
        "opds:v1:start",
    )
    ALL = (START,)


class RootTopLinks:
    """Top Links that only appear at the root."""

    KEEP_READING = TopLink(
        TopRoutes.SERIES,
        Rel.FEATURED,
        MimeType.NAV,
        {
            "topGroup": "s",
            "filters": json.dumps({"bookmark": "UNREAD"}),
            "orderBy": "bookmark_updated_at",
            "orderReverse": True,
        },
        "👀",
        "Keep Reading",
        "Unread issues, recently read first.",
    )
    NEW_UNREAD = TopLink(
        TopRoutes.SERIES,
        Rel.SORT_NEW,
        MimeType.ACQUISITION,
        {
            "topGroup": "s",
            "orderBy": "created_at",
            "orderReverse": True,
        },
        "📥",
        "Latest Unread",
        "Unread issues, latest added first.",
    )
    OLD_UNREAD = TopLink(
        TopRoutes.SERIES,
        Rel.POPULAR,
        MimeType.NAV,
        {
            "topGroup": "s",
            "filters": json.dumps({"bookmark": "UNREAD"}),
            "orderBy": "date",
        },
        "📚",
        "Oldest Unread",
        "Unread issues, oldest published first",
    )
    ALL = (KEEP_READING, NEW_UNREAD, OLD_UNREAD)


@dataclass
class OPDS1Link:
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
    pse_last_read_date: datetime | None = None


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


class FacetGroups:
    """Facet Group definitions."""

    ORDER_BY = FacetGroup(
        "Order By",
        "orderBy",
        "➠",
        (
            Facet("date", "Date"),
            Facet("sort_name", "Name"),
            Facet("filename", "Filename"),
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
        (
            Facet("p", "Publishers View"),
            Facet("s", "Series View"),
            Facet("f", "Folder View"),
            Facet("a", "Story Arc View"),
        ),
    )
    ALL = (TOP_GROUP,)


class OpdsNs:
    """XML Namespaces."""

    CATALOG = "http://opds-spec.org/2010/catalog"
    ACQUISITION = "http://opds-spec.org/2010/acquisition"


@dataclass
class OPDS1EntryObject:
    """Fake entry db object for top link & facet entries."""

    group: str = ""
    ids: frozenset[int] = frozenset()
    name: str = ""
    summary: str = ""
    fake: bool = True
    url_name: str = "opds:v1:feed"


@dataclass
class OPDS1EntryData:
    """Entry Data class to avoid to many args."""

    acquisition_groups: frozenset
    zero_pad: int
    metadata: bool
    mime_type_map: Mapping[str, str]

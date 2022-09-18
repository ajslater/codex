"""OPDS Utility classes."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Union

from comicbox.metadata.comic_json import json
from django.utils.http import urlencode


BLANK_TITLE = "Unknown"


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


class Rel:
    """Link rel strings."""

    AUTHENTICATION = "http://opds-spec.org/auth/document"
    FACET = "http://opds-spec.org/facet"
    ACQUISITION = "http://opds-spec.org/acquisition"
    THUMBNAIL = "http://opds-spec.org/image/thumbnail"
    IMAGE = "http://opds-spec.org/image"
    STREAM = "http://vaemendis.net/opds-pse/stream"
    SORT_NEW = "http://opds-spec.org/sort/new"
    FEATURED = "http://opds-spec.org/featured"
    SELF = "self"
    START = "start"
    UP = "up"
    PREV = "prev"
    NEXT = "next"


class MimeType:
    """Mime Types."""

    ATOM = "application/atom+xml"
    _PROFILE_CATALOG = "profile=opds-catalog"
    NAV = ";".join((ATOM, _PROFILE_CATALOG, "kind=navigation"))
    ACQUISITION = ";".join((ATOM, _PROFILE_CATALOG, "kind=acquisition"))
    AUTHENTICATION = "application/opds-authentication+json"
    OPENSEARCH = "application/opensearchdescription+xml"
    DOWNLOAD = "application/zip"  # PocketBooks needs app/zip
    STREAM = "image/jpeg"


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
    query_params: defaultdict[str, Union[str, bool]]
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
    NEW = TopLink(
        TopRoutes.SERIES,
        Rel.SORT_NEW,
        MimeType.ACQUISITION,
        defaultdict(None, {"orderBy": "date", "orderReverse": True}),
        "📥",
        "Newest Issues",
        "",
    )
    FEATURED = TopLink(
        TopRoutes.SERIES,
        Rel.FEATURED,
        MimeType.NAV,
        defaultdict(
            None, {"orderBy": "date", "filters": json.dumps({"bookmark": "UNREAD"})}
        ),
        "📚",
        "Oldest Unread",
        "Unread issues, oldest first",
    )
    ALL = (START, NEW, FEATURED)


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
    TOP_GROUP = FacetGroup(
        "",
        "topGroup",
        "⊙",
        (Facet("p", "Publishers View"), Facet("s", "Series View")),
    )
    ORDER_REVERSE = FacetGroup(
        "Order",
        "orderReverse",
        "⇕",
        (Facet("false", "Ascending"), Facet("true", "Descending")),
    )
    ALL = (ORDER_BY, TOP_GROUP, ORDER_REVERSE)


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
    type: str
    title: str = ""
    length: int = 0
    facet_group: str = ""
    facet_active: bool = False
    thr_count: int = 0
    pse_count: int = 0
    pse_last_read: int = 0


def update_href_query_params(href, old_query_params, new_query_params):
    """Update an href by masking query params on top of the ones it has."""
    query_params = {}
    for key, value in old_query_params.items():
        # qps are sometimes encapsulated in a list for when there's mutiples.
        if isinstance(value, list):
            if len(value):
                query_params[key] = value[0]
        else:
            query_params[key] = value
    query_params.update(new_query_params)
    if query_params:
        href += "?" + urlencode(query_params, doseq=True)
    return href

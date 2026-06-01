"""
Render internal OPDS feed routes as collection-based URLs.

OPDS view bodies still speak the browse engine's ``{group, pks, page}``
vocabulary (single-char group + parent pks + 1-based page). This is the
single *outbound* edge that renders those as the unified collection URL
``/<collection>[/<parent_ids>][?page=N]`` — the inverse of
:meth:`codex.views.auth.AuthMixin._translate_browser_kwargs`, which
translates the same scheme back on the way in.

Only the browse-feed url_names are rewritten. The manifest / position /
start / binary routes carry no nav ``group`` and reverse unchanged.
``Collection.ROOT`` has no collection of its own; like ``AuthMixin`` it
resolves to its top collection (``publishers``) with no parent ids.
"""

from collections.abc import Mapping
from typing import Any, Final

from django.urls import reverse

from codex.collection import Collection
from codex.views.util import pop_name

# url_names whose ``{group, pks, page}`` kwargs name a browse listing.
FEED_URL_NAMES: Final[frozenset[str]] = frozenset({"opds:v1:feed", "opds:v2:feed"})
# ROOT is not a URL collection; it resolves to its top collection.
ROOT_COLLECTION: Final = "publishers"
_FIRST_PAGE: Final = 1


def _collection_for(group: str) -> str:
    """
    Map a group to its collection segment.

    Every group value the OPDS layer carries is a collection value now;
    ROOT resolves to its top collection.
    """
    return ROOT_COLLECTION if group == Collection.ROOT else group


def opds_feed_reverse(
    url_name: str, kwargs: Mapping, query: Mapping | None = None
) -> str:
    """
    Reverse an OPDS route, mapping feed kwargs to the collection scheme.

    For the browse-feed url_names, ``group`` becomes the ``collection``
    segment, ``pks`` the optional ``parent_ids`` segment (the dummy
    ``0`` / empty root is dropped — root listings omit the segment), and
    ``page`` moves to a ``?page=`` query param (omitted for page 1).
    Every other url_name passes straight through to ``reverse``.
    """
    out_kwargs: dict[str, Any] = dict(pop_name(kwargs))
    out_query: Mapping | None = query
    if url_name in FEED_URL_NAMES and "group" in out_kwargs:
        group = out_kwargs.pop("group")
        pks = out_kwargs.pop("pks", None)
        page = out_kwargs.pop("page", None)
        out_kwargs["collection"] = _collection_for(group)
        if parent_ids := tuple(pk for pk in (pks or ()) if pk):
            out_kwargs["parent_ids"] = parent_ids
        if page is not None and int(page) != _FIRST_PAGE:
            out_query = {**dict(query or {}), "page": page}
    return reverse(url_name, kwargs=out_kwargs, query=out_query)

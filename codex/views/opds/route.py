"""
Render internal OPDS feed routes as collection-based URLs.

OPDS view bodies speak the browse engine's ``{collection, pks, page}``
vocabulary (collection value + parent pks + 1-based page). This is the
single *outbound* edge that renders those as the unified collection URL
``/<collection>[/<parent_ids>][?page=N]`` — the inverse of
:meth:`codex.views.auth.AuthMixin._translate_browser_kwargs`, which
normalizes the same scheme on the way in.

Only the browse-feed url_names are rewritten. The manifest / position /
start / binary routes carry no nav ``collection`` and reverse unchanged.
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


def _collection_for(collection: str) -> str:
    """
    Map an engine collection value to its URL collection segment.

    Every value the OPDS layer carries is a collection value now;
    ROOT resolves to its top collection.
    """
    return ROOT_COLLECTION if collection == Collection.ROOT else collection


def opds_feed_reverse(
    url_name: str, kwargs: Mapping, query: Mapping | None = None
) -> str:
    """
    Reverse an OPDS route, mapping feed kwargs to the collection scheme.

    For the browse-feed url_names, ``collection`` becomes the URL
    ``collection`` segment, ``pks`` the optional ``parent_ids`` segment
    (the dummy ``0`` / empty root is dropped — root listings omit it), and
    ``page`` moves to a ``?page=`` query param (omitted for page 1).
    Every other url_name passes straight through to ``reverse``.

    Every route dict that reaches here — engine kwargs, OPDS masks, the
    persisted ``last_route``, ``DEFAULT_BROWSER_ROUTE``, and redirect
    params — now speaks the ``collection`` dialect.
    """
    out_kwargs: dict[str, Any] = dict(pop_name(kwargs))
    out_query: Mapping | None = query
    if url_name in FEED_URL_NAMES and "collection" in out_kwargs:
        collection = out_kwargs.pop("collection")
        pks = out_kwargs.pop("pks", None)
        page = out_kwargs.pop("page", None)
        out_kwargs["collection"] = _collection_for(collection)
        if parent_ids := tuple(pk for pk in (pks or ()) if pk):
            out_kwargs["parent_ids"] = parent_ids
        if page is not None and int(page) != _FIRST_PAGE:
            out_query = {**dict(query or {}), "page": page}
    return reverse(url_name, kwargs=out_kwargs, query=out_query)

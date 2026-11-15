"""OPDS urls."""

from collections.abc import Callable
from functools import wraps
from typing import Final

from django.http import Http404
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from codex.settings.db import opds_enabled
from codex.urls.const import OPDS_TIMEOUT

# Every view opds_gate wrapped, for the test that no OPDS route is ungated.
_GATED_VIEWS: Final[set[Callable]] = set()


def opds_gate(view: Callable) -> Callable:
    """
    404 the route while the OPDS admin flag is off.

    Wrap it outermost: outside ``cache_page``, so a page cached while OPDS
    was on is not served once it is off, and outside DRF, whose OPDS error
    handler would turn a 404 into a redirect to the start page.
    """

    @wraps(view)
    def gated(request, *args, **kwargs):
        if not opds_enabled():
            raise Http404
        return view(request, *args, **kwargs)

    _GATED_VIEWS.add(gated)
    return gated


def is_opds_gated(view: Callable) -> bool:
    """Whether ``view`` is an :func:`opds_gate` wrapper."""
    return view in _GATED_VIEWS


def opds_cached(view):
    """
    Gate an OPDS feed/manifest/start view, then cache_page + vary headers.

    OPDS accepts Basic, Bearer, and Session auth, so the cache key must
    vary on Cookie and Authorization to keep per-user feeds from leaking
    across users / auth schemes (mirrors ``codex/urls/opds/binary.py``'s
    cover-route composition; sub-plan 01 #1).

    Feed bodies also vary by client User-Agent: ``UserAgentNames``
    switches facet emission (FACET_SUPPORT), download mime types
    (SIMPLE_DOWNLOAD_MIME_TYPES), order facet suppression
    (CLIENT_REORDERS) and absolute hrefs (REQUIRE_ABSOLUTE_URL). Without
    User-Agent in the key, a facet-capable client and a facet-blind one
    served the same URL within the timeout get each other's variant
    (#811). Varying also tells intermediary caches the same.

    Used by ``v1.py``, ``v2.py``, and ``root.py``'s ``/opds/v2.0`` entry.
    Progression and binary routes are NOT cached — see their respective
    modules for the rationale — but are gated. Covers don't vary by
    User-Agent, so the binary routes keep the narrower Cookie/Authorization
    vary.
    """
    return opds_gate(
        cache_page(OPDS_TIMEOUT)(
            vary_on_headers("Cookie", "Authorization", "User-Agent")(view)
        )
    )

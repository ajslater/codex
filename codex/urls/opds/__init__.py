"""OPDS urls."""

from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from codex.urls.const import OPDS_TIMEOUT


def opds_cached(view):
    """
    Wrap an OPDS feed/manifest/start view with cache_page + vary headers.

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
    Progression and binary routes are NOT wrapped — see their respective
    modules for the rationale. Covers don't vary by User-Agent, so the
    binary routes keep the narrower Cookie/Authorization vary.
    """
    return cache_page(OPDS_TIMEOUT)(
        vary_on_headers("Cookie", "Authorization", "User-Agent")(view)
    )

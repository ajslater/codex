"""
OPDS response caching.

``opds_cached`` wraps every feed route in ``cache_page``, but OPDS feed
bodies depend on the client: ``UserAgentNames`` switches facet emission,
download mime types and href absoluteness. These pin that the cache key
and the ``Vary`` header both account for the User-Agent, so one client is
never served a variant rendered for another.
"""

from typing import Final

from django.test import TestCase

from tests.test_opds_feed import (
    _HTTP_OK,
    _V1_START,
    _OPDSFixtureMixin,
)

_YAR_UA: Final = "yar/1.0"  # kybooks, a facet capable client
_FEED: Final = f"{_V1_START}publishers"

# Only ever appears as the opds:facetGroup attribute name, so a plain
# containment check is unambiguous. The internal param names it can
# carry ("orderBy") also appear in facet hrefs, hence matching the
# attribute name rather than its value.
_FACET_MARKER: Final = b"facetGroup"


class OPDSCacheTestCase(_OPDSFixtureMixin, TestCase):
    """The OPDS response cache accounts for the client User-Agent."""

    def test_feed_varies_on_user_agent(self) -> None:
        """The Vary header lets caches key on the client."""
        response = self.client.get(_FEED, headers={"user-agent": _YAR_UA})
        assert response.status_code == _HTTP_OK
        vary = {part.strip().lower() for part in response.headers["Vary"].split(",")}
        assert "user-agent" in vary, response.headers["Vary"]

    def test_cache_not_served_across_user_agents(self) -> None:
        """A feed rendered for one client is never replayed to another."""
        # A facet capable client primes the cache for this URL. The
        # session cookie is shared with the request below, so a key
        # blind to User-Agent matches both.
        first = self.client.get(_FEED, headers={"user-agent": _YAR_UA})
        assert first.status_code == _HTTP_OK
        assert _FACET_MARKER in first.content

        # Well inside OPDS_TIMEOUT, so a stale entry would still be
        # live. This client can't read facets and must not get them.
        second = self.client.get(_FEED)
        assert second.status_code == _HTTP_OK
        assert second.content != first.content
        assert _FACET_MARKER not in second.content

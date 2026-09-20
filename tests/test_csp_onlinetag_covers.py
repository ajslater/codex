"""
Match-candidate cover thumbnails load straight from the source CDNs.

An ``<img>`` load is exempt from CORS, so nothing on Comic Vine's or
Metron's side had to cooperate; codex's own ``img-src`` was the only
thing blocking it. Allowing the two upload paths deletes a server-side
proxy that would have fetched a third-party URL from inside the user's
network, and moves enforcement into the browser, which refuses any host
that is not on the list.

The prefixes are the load-bearing part. A bare host would allow every
path on the API hosts, and a wildcard would allow the web.
"""

from typing import Final

from django.test import TestCase

from codex.settings import SECURE_CSP

_COMICVINE_UPLOADS: Final = "https://comicvine.gamespot.com/a/uploads/"
_METRON_MEDIA: Final = "https://static.metron.cloud/media/"
_TOO_BROAD: Final = (
    "https://comicvine.gamespot.com",
    "https://static.metron.cloud",
    "https:",
    "*",
    "http://comicvine.gamespot.com",
)


class OnlineTagCoverCSPTests(TestCase):
    """``img-src`` allows the two cover CDNs, and nothing wider."""

    def test_both_cdn_prefixes_are_allowed(self) -> None:
        sources = SECURE_CSP["img-src"]
        assert _COMICVINE_UPLOADS in sources, sources
        assert _METRON_MEDIA in sources, sources

    def test_no_bare_host_or_wildcard(self) -> None:
        """A prefix is the control; widening it to a host gives it away."""
        sources = set(SECURE_CSP["img-src"])
        for source in _TOO_BROAD:
            assert source not in sources, source

    def test_existing_sources_survive_the_overlay(self) -> None:
        """The merge is per directive, so nothing else in img-src moves."""
        sources = {str(source) for source in SECURE_CSP["img-src"]}
        assert "'self'" in sources, sources
        assert "data:" in sources, sources
        assert any("pdfjs-dist" in source for source in sources), sources

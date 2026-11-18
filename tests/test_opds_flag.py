"""
The OPDS admin flag.

What these tests pin:

* With the flag on, OPDS serves as before.
* With it off, every OPDS route is a plain 404: not the OPDS error
  handler's redirect to the start page, not the catch-all's redirect home,
  and not a feed cached while the flag was on.
* Every route under ``/opds/``, and the bare ``/opds`` redirect, is wrapped
  in :func:`codex.urls.opds.opds_gate`, so a new route cannot skip it.
"""

from collections.abc import Iterator
from typing import Final, override
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.startup import init_admin_flags
from codex.urls.opds import is_opds_gated
from codex.views.opds.v2.feed import OPDS2StartView

_HTTP_OK: Final = 200
_HTTP_NOT_FOUND: Final = 404
_OFF_URLS: Final = (
    "/opds",
    "/opds/",
    "/opds/v1.2/",
    "/opds/v1.2/publishers",
    "/opds/v1.2/opensearch/v1.1",
    "/opds/v2.0",
    "/opds/v2.0/",
    "/opds/v2.0/catalog",
    "/opds/v2.0/series/1",
    "/opds/v2.0/c/1/1",
    "/opds/v2.0/comics/1/position",
    "/opds/auth",
    "/opds/auth/v1",
    "/opds/bin/c/1/cover.webp",
    "/opds/bin/c/1/1/page.jpg",
    "/opds/bin/custom_cover/1/cover.webp",
    "/opds/bin/c/1/download/comic.cbz",
)


def _set_opds(*, on: bool) -> None:
    AdminFlag.objects.filter(key=AdminFlagChoices.OPDS.value).update(on=on)


class OPDSFlagTestCase(TestCase):
    """The flag turns OPDS off entirely."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        # Anonymous browsing on, so a 200 needs no credential.
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=True)

    def test_on_serves(self) -> None:
        assert Client().get("/opds/v2.0/").status_code == _HTTP_OK
        assert Client().get("/opds/v1.2/").status_code == _HTTP_OK

    def test_off_is_a_404_everywhere(self) -> None:
        _set_opds(on=False)
        for url in _OFF_URLS:
            response = Client().get(url)
            assert response.status_code == _HTTP_NOT_FOUND, (url, response)

    def test_a_feed_cached_while_on_is_not_served_once_off(self) -> None:
        assert Client().get("/opds/v2.0/").status_code == _HTTP_OK
        # Served from the page cache: the view does not run again.
        with patch.object(OPDS2StartView, "get", side_effect=AssertionError):
            assert Client().get("/opds/v2.0/").status_code == _HTTP_OK

        _set_opds(on=False)

        assert Client().get("/opds/v2.0/").status_code == _HTTP_NOT_FOUND

    def test_on_again_serves_again(self) -> None:
        _set_opds(on=False)
        assert Client().get("/opds/v2.0/").status_code == _HTTP_NOT_FOUND
        _set_opds(on=True)
        assert Client().get("/opds/v2.0/").status_code == _HTTP_OK


def _patterns(patterns) -> Iterator[URLPattern]:
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _patterns(pattern.url_patterns)
        else:
            yield pattern


class OPDSGateStructureTestCase(SimpleTestCase):
    """No OPDS route escapes the gate."""

    def test_every_opds_route_is_gated(self) -> None:
        (opds,) = (
            pattern
            for pattern in get_resolver().url_patterns
            if isinstance(pattern, URLResolver) and pattern.namespace == "opds"
        )
        routes = tuple(_patterns(opds.url_patterns))
        assert routes
        for route in routes:
            assert is_opds_gated(route.callback), route

    def test_the_bare_opds_redirect_is_gated(self) -> None:
        (bare,) = (
            pattern
            for pattern in get_resolver().url_patterns
            if isinstance(pattern, URLPattern) and str(pattern.pattern) == "opds"
        )
        assert is_opds_gated(bare.callback)

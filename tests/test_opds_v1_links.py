"""
OPDS v1 start entries, facets and head links, and the OPDS cache key.

* A start-page entry's description never rendered: ``summary`` read
  ``child_count`` off the fake entry object, the AttributeError made DRF
  skip the field, and the ``<content>`` element was never written.
* The start links said ``orderReverse=True`` and the Order Direction facet
  is ``true``, so the facet never marked itself active.
* Facet clients got one untitled ``featured`` head link per start link
  and shelf, and the shelves were queried once per use.
* With remote-user auth the feed cache did not vary on ``Remote-User``,
  so one proxied user's feed could be served to another's.
"""

import xml.etree.ElementTree as ET
from typing import Final
from unittest.mock import patch
from urllib.parse import urlsplit

from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext

from codex.models import Shelf, ShelfItem
from tests.test_opds_keep_reading import (
    _ATOM_NS,
    _TEST_PASSWORD,
    _V1_START,
    KeepReadingSeedTestCase,
    _v1_entry_href,
)

_HTTP_OK: Final = 200
_FACET_UA: Final = "Panels/3.13"
_FEATURED: Final = "http://opds-spec.org/featured"
_LATEST_UNREAD: Final = "Latest Unread"


def _opds_attr(link: ET.Element, name: str) -> str | None:
    """Read an ``opds:`` attribute; the namespace differs by feed kind."""
    return next(
        (value for key, value in link.attrib.items() if key.endswith(f"}}{name}")),
        None,
    )


class OPDS1LinksTestCase(KeepReadingSeedTestCase):
    """The v1 feed as a facet-capable client reads it."""

    def _get(self, url: str, **headers) -> ET.Element:
        cache.clear()
        response = self.client.get(url, **headers)
        assert response.status_code == _HTTP_OK, response.content[:300]
        return ET.fromstring(response.content)  # noqa: S314

    def _login(self) -> None:
        assert self.client.login(username=self.user.username, password=_TEST_PASSWORD)

    def test_start_entries_carry_their_description(self) -> None:
        root = self._get(_V1_START)
        entry = next(
            e
            for e in root.iter(f"{_ATOM_NS}entry")
            if (e.findtext(f"{_ATOM_NS}title") or "").endswith(_LATEST_UNREAD)
        )
        assert entry.findtext(f"{_ATOM_NS}content"), ET.tostring(entry)

    def test_the_descending_facet_is_active_after_a_descending_link(self) -> None:
        self._login()
        cache.clear()
        start = self.client.get(_V1_START, HTTP_USER_AGENT=_FACET_UA).content
        href = _v1_entry_href(start, _LATEST_UNREAD)
        assert href
        split = urlsplit(href)
        assert "orderReverse=true" in split.query, split.query

        root = self._get(f"{split.path}?{split.query}", HTTP_USER_AGENT=_FACET_UA)
        direction = {
            link.get("title"): _opds_attr(link, "activeFacet")
            for link in root.iter(f"{_ATOM_NS}link")
            if _opds_attr(link, "facetGroup") == "Order Direction"
        }
        assert direction == {"Order Ascending": None, "Order Descending": "true"}, (
            direction
        )

    def _shelve_one(self) -> None:
        shelf = Shelf.objects.create(user=self.user, name="Want to Read")
        ShelfItem.objects.create(
            shelf=shelf, collection="comics", target_id=self.comics[0].pk
        )

    def test_head_links_are_titled(self) -> None:
        self._shelve_one()
        self._login()
        root = self._get(_V1_START, HTTP_USER_AGENT=_FACET_UA)
        featured = [
            link
            for link in root.findall(f"{_ATOM_NS}link")
            if link.get("rel") == _FEATURED
        ]
        assert featured
        assert all(link.get("title") for link in featured), [
            link.attrib for link in featured
        ]

    def test_shelves_are_read_once_per_feed(self) -> None:
        self._shelve_one()
        self._login()
        with CaptureQueriesContext(connection) as ctx:
            self._get(_V1_START, HTTP_USER_AGENT=_FACET_UA)
        shelf_reads = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].startswith('SELECT DISTINCT "codex_shelf"."id"')
        ]
        assert len(shelf_reads) == 1, shelf_reads


def _vary(*, remote_user: bool) -> str:
    from codex.urls import opds

    cache.clear()
    with (
        override_settings(AUTH_REMOTE_USER=remote_user),
        patch.object(opds, "opds_enabled", return_value=True),
    ):
        view = opds.opds_cached(lambda _request: HttpResponse("feed"))
        return view(RequestFactory().get("/opds/v1.2/"))["Vary"]


def test_the_feed_cache_varies_on_remote_user_when_it_is_on() -> None:
    """A proxied user's feed is keyed by the user the proxy names."""
    assert "Remote-User" in _vary(remote_user=True)


def test_the_feed_cache_does_not_vary_on_remote_user_when_it_is_off() -> None:
    """Without remote-user auth the header names nobody."""
    assert "Remote-User" not in _vary(remote_user=False)

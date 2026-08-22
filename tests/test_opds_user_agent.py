"""
OPDS v1 behavior that varies by client User-Agent.

``UserAgentNames`` (``codex/views/opds/const.py``) switches how sort
options reach a client: facet-aware readers get real ``opds:facetGroup``
links, everyone else gets them hacked in as fake navigation folders.
These pin both variants, the human-readable facet group names, and
that the User-Agent itself parses to the client name Codex matches on.
"""

import xml.etree.ElementTree as ET
from typing import Final

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from rest_framework.request import Request

from codex.views.opds.user_agent import get_user_agent_name
from tests.test_opds_feed import (
    _HTTP_OK,
    _V1_START,
    _OPDSFixtureMixin,
)

# Panels sends a CFNetwork style UA; the name is the part before the
# first slash and the build number follows it. iOS builds (952+) render
# OPDS facets natively; the macOS build (951) does not.
_PANELS_UA: Final = "Panels/952 CFNetwork/3896.100.1.2.1 Darwin/27.0.0"
_PANELS_MACOS_UA: Final = "Panels/951 CFNetwork/3896.100.1.2.1 Darwin/25.0.0"
_YAR_UA: Final = "yar/1.0"  # kybooks
_FACET_UAS: Final = (_YAR_UA, _PANELS_UA)

# A non-start feed: start pages emit the topCollection group instead of
# the order groups.
_FEED: Final = f"{_V1_START}publishers"

_FACET_REL: Final = "http://opds-spec.org/facet"
_ORDER_BY_ENTRY_TITLE: Final = "➠ Order By Date"
_ORDER_REVERSE_ENTRY_TITLE: Final = "⇕ Order Ascending"
# The internal query param names that used to leak into facetGroup.
_QUERY_PARAM_NAMES: Final = frozenset({"orderBy", "orderReverse", "topCollection"})


def _local_name(tag: str) -> str:
    """Strip any XML namespace from a tag or attribute name."""
    return tag.rsplit("}", 1)[-1]


def _feed_links(content: bytes) -> list[ET.Element]:
    """Every feed level ``<link>`` (entry links excluded)."""
    root = ET.fromstring(content)  # noqa: S314 - server-rendered, trusted
    return [el for el in root if _local_name(el.tag) == "link"]


def _facet_groups(content: bytes) -> set[str]:
    """
    Every ``opds:facetGroup`` attribute value in the feed.

    Matched by local name because the ``opds:`` namespace URI differs
    between catalog and acquisition feeds.
    """
    root = ET.fromstring(content)  # noqa: S314 - server-rendered, trusted
    return {
        value
        for el in root.iter()
        for name, value in el.attrib.items()
        if _local_name(name) == "facetGroup"
    }


def _entries(content: bytes) -> list[ET.Element]:
    """Every ``<entry>`` element."""
    root = ET.fromstring(content)  # noqa: S314 - server-rendered, trusted
    return [el for el in root if _local_name(el.tag) == "entry"]


def _entry_titles(content: bytes) -> list[str]:
    """Collect the title text of every ``<entry>``."""
    titles = []
    for entry in _entries(content):
        titles.extend(
            (child.text or "").strip()
            for child in entry
            if _local_name(child.tag) == "title"
        )
    return titles


class OPDSv1UserAgentTestCase(_OPDSFixtureMixin, TestCase):
    """Facet emission varies by client User-Agent."""

    def test_facet_ua_gets_facet_links_no_fake_entries(self) -> None:
        """Facet-aware clients get real facet links and no fake folders."""
        for user_agent in _FACET_UAS:
            with self.subTest(user_agent=user_agent):
                # Same URL and session cookie as the previous iteration:
                # without this the cache would answer for the other UA.
                cache.clear()
                response = self.client.get(_FEED, headers={"user-agent": user_agent})
                assert response.status_code == _HTTP_OK

                facet_links = [
                    link
                    for link in _feed_links(response.content)
                    if link.get("rel") == _FACET_REL
                ]
                assert facet_links, "no facet links for a facet-capable client"

                titles = _entry_titles(response.content)
                assert not [
                    title
                    for title in titles
                    if "Order By" in title or "➠" in title or "⇕" in title
                ], titles

                # The old duplicate facet entries serialized to nothing:
                # an empty <id> and no <link> children. Every real entry
                # is navigable.
                for entry in _entries(response.content):
                    links = [el for el in entry if _local_name(el.tag) == "link"]
                    assert links, ET.tostring(entry)

    def test_default_ua_gets_fake_sort_entries_no_facet_links(self) -> None:
        """Facet-blind clients still get sort options as nav folders."""
        response = self.client.get(_FEED)
        assert response.status_code == _HTTP_OK

        assert not [
            link
            for link in _feed_links(response.content)
            if link.get("rel") == _FACET_REL
        ]
        assert not _facet_groups(response.content)

        titles = _entry_titles(response.content)
        assert _ORDER_BY_ENTRY_TITLE in titles, titles
        assert _ORDER_REVERSE_ENTRY_TITLE in titles, titles

    def test_facet_blind_panels_build_gets_fake_entries(self) -> None:
        """Panels builds below the facet floor keep the nav folder sort."""
        response = self.client.get(_FEED, headers={"user-agent": _PANELS_MACOS_UA})
        assert response.status_code == _HTTP_OK

        assert not [
            link
            for link in _feed_links(response.content)
            if link.get("rel") == _FACET_REL
        ]
        assert not _facet_groups(response.content)

        titles = _entry_titles(response.content)
        assert _ORDER_BY_ENTRY_TITLE in titles, titles
        assert _ORDER_REVERSE_ENTRY_TITLE in titles, titles

    def test_facet_group_display_names(self) -> None:
        """Facet groups are display strings, not internal query params."""
        cache.clear()
        response = self.client.get(_FEED, headers={"user-agent": _YAR_UA})
        assert response.status_code == _HTTP_OK
        groups = _facet_groups(response.content)
        assert groups == {"Order By", "Order Direction"}, groups
        assert not groups & _QUERY_PARAM_NAMES

        cache.clear()
        response = self.client.get(_V1_START, headers={"user-agent": _YAR_UA})
        assert response.status_code == _HTTP_OK
        groups = _facet_groups(response.content)
        assert groups == {"Views"}, groups
        assert not groups & _QUERY_PARAM_NAMES

        # The start page top links remain entries; the view facets do not.
        titles = _entry_titles(response.content)
        assert "⊙ Publishers View" not in titles, titles
        assert "Publishers View" not in titles, titles


def _user_agent(user_agent: str | None) -> tuple[str, int | None]:
    """Parse a raw header value the way a request would deliver it."""
    headers = {} if user_agent is None else {"user-agent": user_agent}
    return get_user_agent_name(Request(RequestFactory().get("/", headers=headers)))


def test_get_user_agent_name_panels() -> None:
    """Panels' CFNetwork UA parses to its client name and build."""
    assert _user_agent(_PANELS_UA) == ("Panels", 952)
    assert _user_agent(_PANELS_MACOS_UA) == ("Panels", 951)


def test_get_user_agent_name_panels_unparseable_build() -> None:
    """A Panels UA without a numeric build parses to no build."""
    assert _user_agent("Panels/beta CFNetwork/1.0") == ("Panels", None)
    assert _user_agent("Panels") == ("Panels", None)


def test_get_user_agent_name_kybooks() -> None:
    """Only clients with build floors get a build parse."""
    assert _user_agent(_YAR_UA) == ("yar", None)


def test_get_user_agent_name_missing() -> None:
    """A missing User-Agent parses to the empty name."""
    assert _user_agent(None) == ("", None)


def test_get_user_agent_name_no_version() -> None:
    """A UA without a version is its own name."""
    assert _user_agent("Weird") == ("Weird", None)

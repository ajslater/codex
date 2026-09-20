"""
OPDS v1 behavior that varies by client User-Agent.

``UserAgentNames`` (``codex/views/opds/const.py``) switches how *sort*
options reach a client: facet-aware readers get real ``opds:facetGroup``
links, everyone else gets them hacked in as fake navigation folders.
These pin both variants, the human-readable facet group names, and
that the User-Agent itself parses to the client name Codex matches on.

Navigation does not vary. The start feed's entry list must be identical
for every client and must reach the library on its own, because a reader
that ignores facet links would otherwise have no way in (#855).
"""

import re
import xml.etree.ElementTree as ET
from typing import Final

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from rest_framework.request import Request

from codex.views.opds.user_agent import get_user_agent_name
from tests.opds_schema import validate_opds1
from tests.test_opds_feed import (
    _HTTP_OK,
    _V1_START,
    _OPDSFixtureMixin,
)

# Panels sends a CFNetwork style UA; the client name is the part before
# the first slash, which is all codex parses. The build that follows used
# to gate facets, until the real user agents below showed macOS 957 and
# iOS 956 — one apart, interleaved, with identical Darwin tokens. Panels
# renders facets on iOS only, so codex sends it both the facet links and
# the navigation folder sort rather than guessing (#855).
_PANELS_MACOS_UA: Final = "Panels/957 CFNetwork/3896.100.1.1.1 Darwin/27.0.0"
_PANELS_IOS_UA: Final = "Panels/956 CFNetwork/3896.100.1.2.1 Darwin/27.0.0"
# A dotted version used to parse to no build at all; nothing reads it now.
_PANELS_ODD_UA: Final = "Panels/beta CFNetwork/3896.100.1.2.1 Darwin/27.0.0"
_PANELS_UAS: Final = (_PANELS_MACOS_UA, _PANELS_IOS_UA, _PANELS_ODD_UA)
_YAR_UA: Final = "yar/1.0"  # kybooks
# Every client, however it renders facets, gets the same start feed.
_UA_MATRIX: Final = (None, _YAR_UA, _PANELS_MACOS_UA, _PANELS_IOS_UA, _PANELS_ODD_UA)
_PUBLISHERS_VIEW_TITLE: Final = "\u2299 Publishers View"

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


# Titles the facet-blind fallback synthesizes as nav folders. A facet-aware
# client must not see any of them.
_FAKE_SORT_RE: Final = re.compile("Order By|\u27a0|\u21d5")


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


def _entry_hrefs(content: bytes) -> list[str]:
    """
    Collect hrefs of ``<link>`` elements *inside* entries.

    Feed level links are excluded on purpose: a catalog reachable only
    by a facet link is not reachable by a client that ignores them.
    """
    hrefs = []
    for entry in _entries(content):
        hrefs.extend(
            href
            for child in entry
            if _local_name(child.tag) == "link" and (href := child.get("href"))
        )
    return hrefs


class OPDSv1UserAgentTestCase(_OPDSFixtureMixin, TestCase):
    """Facet emission varies by client User-Agent."""

    def _assert_facet_feed(self, content: bytes) -> None:
        """Assert facet links exist and no fake sort entries or stub entries do."""
        facet_links = [
            link for link in _feed_links(content) if link.get("rel") == _FACET_REL
        ]
        assert facet_links, "no facet links for a facet-capable client"

        titles = _entry_titles(content)
        assert not [title for title in titles if _FAKE_SORT_RE.search(title)], titles

        # The old duplicate facet entries serialized to nothing: an empty
        # <id> and no <link> children. Every real entry is navigable.
        for entry in _entries(content):
            links = [el for el in entry if _local_name(el.tag) == "link"]
            assert links, ET.tostring(entry)

    def test_facet_aware_client_gets_facet_links_no_fake_entries(self) -> None:
        """Kybooks renders facet links, so it must not also get fake folders."""
        cache.clear()
        response = self.client.get(_FEED, headers={"user-agent": _YAR_UA})
        assert response.status_code == _HTTP_OK
        self._assert_facet_feed(response.content)

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

    def test_panels_gets_facet_links_and_sort_entries(self) -> None:
        """
        Panels gets both treatments, whatever build it is.

        iOS renders the facet links and macOS ignores them, and nothing
        in the User-Agent separates the two, so codex stops choosing:
        every Panels build receives the links *and* the navigation
        folder sort. The redundant rows on iOS are the accepted cost of
        macOS having any sort at all (#855).
        """
        for user_agent in _PANELS_UAS:
            with self.subTest(user_agent=user_agent):
                cache.clear()
                response = self.client.get(_FEED, headers={"user-agent": user_agent})
                assert response.status_code == _HTTP_OK

                facet_links = [
                    link
                    for link in _feed_links(response.content)
                    if link.get("rel") == _FACET_REL
                ]
                assert facet_links, "no facet links for Panels"

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
        # The root Views group is navigation, not a facet (#855), so a
        # facet-aware client gets no facet groups on the start page at
        # all — it gets the views as entries like everyone else.
        assert not _facet_groups(response.content)
        titles = _entry_titles(response.content)
        assert _PUBLISHERS_VIEW_TITLE in titles, titles

    def test_start_entries_identical_for_every_user_agent(self) -> None:
        """
        Navigation must not depend on the User-Agent.

        The start feed carries no entries of its own, so the four View
        rows are the only way into the library from it. Emitting them as
        facet links for some clients is what left macOS Panels with three
        dead-end rows (#855). Fails loudly the instant anyone re-couples
        navigation to ``use_facets``.
        """
        baseline = None
        for user_agent in _UA_MATRIX:
            with self.subTest(user_agent=user_agent):
                cache.clear()
                headers = {} if user_agent is None else {"user-agent": user_agent}
                response = self.client.get(_V1_START, headers=headers)
                assert response.status_code == _HTTP_OK
                assert not validate_opds1(response.content)

                titles = _entry_titles(response.content)
                assert _PUBLISHERS_VIEW_TITLE in titles, titles
                # No sort facets on the start page for anyone, so the
                # entry list is the same for every client.
                assert not _facet_groups(response.content)
                if baseline is None:
                    baseline = titles
                assert titles == baseline, (user_agent, titles, baseline)

    def test_start_entries_reach_the_library_for_every_user_agent(self) -> None:
        """
        Entries alone must reach the library, ignoring feed level links.

        Titles prove a row rendered; only following it proves the row
        goes anywhere. ``test_walk_all_feeds_resolve`` cannot catch this
        class of bug because it walks feed level facet links too.
        """
        for user_agent in _UA_MATRIX:
            with self.subTest(user_agent=user_agent):
                cache.clear()
                headers = {} if user_agent is None else {"user-agent": user_agent}
                response = self.client.get(_V1_START, headers=headers)
                assert response.status_code == _HTTP_OK

                found = False
                for href in _entry_hrefs(response.content):
                    cache.clear()
                    followed = self.client.get(href, headers=headers)
                    if (
                        followed.status_code == _HTTP_OK
                        and b"PubOne" in followed.content
                    ):
                        found = True
                        break
                assert found, "no entry on the start feed reaches the library"


def _user_agent(user_agent: str | None) -> str:
    """Parse a raw header value the way a request would deliver it."""
    headers = {} if user_agent is None else {"user-agent": user_agent}
    return get_user_agent_name(Request(RequestFactory().get("/", headers=headers)))


def test_get_user_agent_name_panels() -> None:
    """Every Panels UA parses to the same client name; no build is read."""
    assert _user_agent(_PANELS_MACOS_UA) == "Panels"
    assert _user_agent(_PANELS_IOS_UA) == "Panels"
    assert _user_agent(_PANELS_ODD_UA) == "Panels"
    assert _user_agent("Panels") == "Panels"


def test_get_user_agent_name_kybooks() -> None:
    """The name is everything before the first slash."""
    assert _user_agent(_YAR_UA) == "yar"


def test_get_user_agent_name_missing() -> None:
    """A missing User-Agent parses to the empty name."""
    assert _user_agent(None) == ""


def test_get_user_agent_name_no_version() -> None:
    """A UA without a version is its own name."""
    assert _user_agent("Weird") == "Weird"

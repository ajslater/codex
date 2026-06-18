"""
Functional OPDS feed-resolution tests for v1 (Atom XML) and v2 (JSON).

There is no other functional OPDS suite. These pin that the catalog
*resolves* — every server-emitted navigation / subsection / next / up
href can be followed back to a ``200`` — independent of the URL
vocabulary. They walk the feed by following whatever links the server
emits rather than asserting hardcoded paths, so they survive the
group→collection URL flip (Phase 5): green on the legacy single-char
scheme and green again on the collection scheme.
"""

import shutil
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models import (
    AdminFlag,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_REDIRECT: Final = 300
_HTTP_ERROR: Final = 400  # 2xx/3xx are healthy; >= 400 is a broken link
_TMP_DIR: Final = Path("/tmp/codex.tests.opds")  # noqa: S108

_V1_START: Final = "/opds/v1.2/"
_V2_START: Final = "/opds/v2.0/"

# Each walk stays within its own version root so the XML / JSON parser
# matches the feed it follows. Binary (``/opds/bin/``), auth
# (``/opds/auth/``), opensearch descriptions, the progression endpoint
# and URI-template hrefs (``{?query}``) are not followable browse feeds.
_MAX_VISITS: Final = 80
_MIN_WALK_VISITS: Final = 3  # a real traversal descends past root + a couple feeds


def _local_link_tag(tag: str) -> str:
    """Strip any XML namespace from an element tag."""
    return tag.rsplit("}", 1)[-1]


def _v1_links(content: bytes) -> list[tuple[str | None, str]]:
    """(rel, href) for every ``<link>`` in an Atom feed (feed + entries)."""
    root = ET.fromstring(content)  # noqa: S314 - server-rendered, trusted
    return [
        (el.get("rel"), href)
        for el in root.iter()
        if _local_link_tag(el.tag) == "link" and (href := el.get("href"))
    ]


def _v2_links(node) -> list[tuple[str | None, str]]:
    """(rel, href) for every link object in a parsed OPDS 2.0 JSON feed."""
    links: list[tuple[str | None, str]] = []
    if isinstance(node, dict):
        href = node.get("href")
        if isinstance(href, str):
            links.append((node.get("rel"), href))
        for value in node.values():
            links.extend(_v2_links(value))
    elif isinstance(node, list):
        for item in node:
            links.extend(_v2_links(item))
    return links


def _followable(href: str, root: str) -> str | None:
    """Return a GET-able path+query for a same-version browse feed, else None."""
    if "{" in href:  # URI template, e.g. the search link's "{?query}"
        return None
    parts = urlsplit(href)  # tolerate absolute URLs (DEBUG / some readers)
    path = parts.path
    if not path.startswith(root):
        return None
    if "/opensearch" in path or "/position" in path:
        return None
    return f"{path}?{parts.query}" if parts.query else path


def _response_links(
    response, parse: Callable[[object], list[tuple[str | None, str]]], root: str
) -> tuple[set[str], list[str]]:
    """
    Return the (rels, followable paths) a feed response contributes.

    A ``2xx`` is parsed for its links; a ``3xx`` contributes only its
    redirect target (the engine self-correcting to a valid route);
    a ``>= 400`` contributes nothing.
    """
    code = response.status_code
    if code == _HTTP_OK:
        pairs = parse(response)
    elif _HTTP_REDIRECT <= code < _HTTP_ERROR:
        pairs = [(None, response.headers.get("Location", ""))]
    else:
        return set(), []
    rels = {rel for rel, _href in pairs if isinstance(rel, str)}
    follows = [follow for _rel, href in pairs if (follow := _followable(href, root))]
    return rels, follows


_COLLECTIONS: Final = frozenset(
    {"publishers", "imprints", "series", "volumes", "comics", "folders", "arcs"}
)


def _first_segment(path: str, root: str) -> str:
    """Return the first path segment below the version root (query stripped)."""
    return path[len(root) :].split("?", 1)[0].split("/", 1)[0]


def _assert_collection_scheme(paths: Iterable[str], root: str) -> None:
    """Pin that emitted feed URLs use the collection scheme, not the legacy one."""
    paths = list(paths)
    segments = {_first_segment(p, root) for p in paths}
    assert _COLLECTIONS & segments, f"no collection segment among {segments}"
    for path in paths:
        # "" is the catalog root; "c" is the v2 manifest's intentional
        # literal route (it never used the single-char group converter).
        segment = _first_segment(path, root)
        assert segment in _COLLECTIONS or segment in {"", "c"}, (
            f"legacy group segment {segment!r} in {path}"
        )
        no_query = path.split("?", 1)[0]
        assert "/0/" not in no_query, f"dummy-0 root sentinel in {path}"
        assert not no_query.endswith("/0"), f"dummy-0 root sentinel in {path}"


class _OPDSFixtureMixin:
    """One publisher hierarchy + a folder, behind an authed client."""

    def setUp(self) -> None:
        # Browser feeds go through cachalot; clear so a prior test's
        # cached rows don't mask this fixture.
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)

        self.user = User.objects.create_user(username="opds", password=_TEST_PASSWORD)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client.force_login(self.user)

        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="PubOne")
        imprint = Imprint.objects.create(name="ImpOne", publisher=publisher)
        folder_dir = _TMP_DIR / "folder1"
        folder_dir.mkdir(exist_ok=True)
        folder = Folder.objects.create(library=library, path=str(folder_dir))

        # Two series so a lowered page size yields a real "next" link.
        for s_idx in (1, 2):
            series = Series.objects.create(
                name=f"SeriesNo{s_idx}", publisher=publisher, imprint=imprint
            )
            volume = Volume.objects.create(
                name="1", publisher=publisher, imprint=imprint, series=series
            )
            for c_idx in (1, 2):
                path = folder_dir / f"s{s_idx}c{c_idx}.cbz"
                path.touch()
                comic = Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=c_idx,
                    name=f"Comic-S{s_idx}-{c_idx}",
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    parent_folder=folder,
                    # Set so OPDS never opens the (empty) archive:
                    # lazy_metadata short-circuits when both are present.
                    file_type="CBZ",
                    page_count=1,
                    size=1,
                )
                comic.folders.set([folder])
        self.publisher_pk = publisher.pk  # pyright: ignore[reportUninitializedInstanceVariable]

    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _walk(
        self, start: str, parse: Callable[[object], list[tuple[str | None, str]]]
    ) -> tuple[dict[str, int], set[str], bytes]:
        """
        Breadth-first follow every emitted browse-feed href from ``start``.

        A ``2xx`` is parsed and descended into; a ``3xx`` is a valid
        self-correcting redirect (the engine steering a client off an
        unavailable nav collection) whose target is enqueued and verified.
        Only ``>= 400`` counts as a broken link. Returns the per-path
        status map, the set of link ``rel`` values seen, and the
        concatenated ``2xx`` bodies (for content checks).
        """
        seen: set[str] = set()
        queue: deque[str] = deque([start])
        statuses: dict[str, int] = {}
        rels: set[str] = set()
        body = bytearray()
        while queue and len(seen) < _MAX_VISITS:
            path = queue.popleft()
            if path in seen:
                continue
            seen.add(path)
            response = self.client.get(path)
            statuses[path] = response.status_code
            if response.status_code == _HTTP_OK:
                body.extend(response.content)
            new_rels, follows = _response_links(response, parse, start)
            rels |= new_rels
            queue.extend(follow for follow in follows if follow not in seen)
        return statuses, rels, bytes(body)


class OPDSv1FeedTestCase(_OPDSFixtureMixin, TestCase):
    """OPDS 1.2 (Atom XML) feed resolution."""

    @staticmethod
    def _parse(response) -> list[tuple[str | None, str]]:
        return _v1_links(response.content)

    def test_start_resolves(self) -> None:
        """The v1.2 catalog root returns a non-empty Atom feed."""
        response = self.client.get(_V1_START)
        assert response.status_code == _HTTP_OK, response.content
        assert _v1_links(response.content), "start feed emitted no links"

    def test_walk_all_feeds_resolve(self) -> None:
        """Every nav/subsection/next/up href reachable from root → 200."""
        statuses, _rels, body = self._walk(_V1_START, self._parse)
        bad = {path: code for path, code in statuses.items() if code >= _HTTP_ERROR}
        assert not bad, bad
        assert len(statuses) > _MIN_WALK_VISITS, "walk did not traverse the catalog"
        # Real listing content surfaces, not just empty 200 shells.
        assert b"SeriesNo1" in body, "series row never appeared in any feed"
        # The flip landed: collection segments, no dummy-0, no char groups.
        _assert_collection_scheme(statuses, _V1_START)

    def test_pagination_emits_followable_next(self) -> None:
        """With page size 1, a multi-row listing emits a resolvable next."""
        AdminFlag.objects.filter(
            key=AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value
        ).update(value="1")
        cache.clear()
        statuses, rels, _body = self._walk(_V1_START, self._parse)
        bad = {path: code for path, code in statuses.items() if code >= _HTTP_ERROR}
        assert not bad, bad
        assert "next" in rels, "no next link despite a paginated listing"


class OPDSv2FeedTestCase(_OPDSFixtureMixin, TestCase):
    """OPDS 2.0 (JSON) feed resolution."""

    @staticmethod
    def _parse(response) -> list[tuple[str | None, str]]:
        return _v2_links(response.json())

    def test_start_resolves(self) -> None:
        """The v2.0 catalog root returns a non-empty JSON feed."""
        response = self.client.get(_V2_START)
        assert response.status_code == _HTTP_OK, response.content
        assert _v2_links(response.json()), "start feed emitted no links"

    def test_walk_all_feeds_resolve(self) -> None:
        """Every emitted browse-feed href reachable from root → 200."""
        statuses, _rels, body = self._walk(_V2_START, self._parse)
        bad = {path: code for path, code in statuses.items() if code >= _HTTP_ERROR}
        assert not bad, bad
        assert len(statuses) > _MIN_WALK_VISITS, "walk did not traverse the catalog"
        assert b"SeriesNo1" in body, "series row never appeared in any feed"
        # The flip landed: collection segments, no dummy-0, no char groups.
        _assert_collection_scheme(statuses, _V2_START)

    def test_pagination_emits_followable_next(self) -> None:
        """With page size 1, a multi-row listing emits a resolvable next."""
        AdminFlag.objects.filter(
            key=AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value
        ).update(value="1")
        cache.clear()
        statuses, rels, _body = self._walk(_V2_START, self._parse)
        bad = {path: code for path, code in statuses.items() if code >= _HTTP_ERROR}
        assert not bad, bad
        assert "next" in rels, "no next link despite a paginated listing"

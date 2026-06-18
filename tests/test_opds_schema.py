"""
OPDS schema-compliance tests for v1.2 (Atom XML) and v2.0 (JSON).

The sibling ``tests/test_opds_feed.py`` proves the catalog *resolves* (every
href → 2xx). This suite proves it is *spec-shaped*: every feed the server emits
is validated against the official OPDS schemas (see ``tests/opds_schema.py`` and
the vendored specs under ``tests/schema/opds/``). This is what a rigorous OPDS
2.0 client (e.g. Stump) checks before it will render a feed.

The walk follows whatever links the server emits — feeds get validated against
the OPDS feed schema, publication manifests (the ``c/`` route) against the
Readium webpub-manifest schema — so coverage tracks the real catalog rather than
a hardcoded URL list.
"""

import re
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Callable, Iterator
from http import HTTPStatus
from typing import Any, override
from urllib.parse import urlparse

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from codex.models import (
    Bookmark,
    Character,
    Comic,
    Credit,
    CreditPerson,
    CreditRole,
    Genre,
    Identifier,
    IdentifierSource,
    Language,
    Location,
    SeriesGroup,
    StoryArc,
    StoryArcNumber,
    Tag,
    Team,
)
from codex.models.identifier import IdentifierType
from codex.views.opds.const import MimeType, Rel
from tests.opds_schema import (
    validate_divina_profile,
    validate_opds1,
    validate_opds2_feed,
    validate_opds2_manifest,
    validate_opds_authentication,
    validate_opds_progression,
    validate_opds_pse,
    validate_opensearch,
    validate_v2_authenticate,
)
from tests.test_opds_feed import (
    _HTTP_OK,
    _MAX_VISITS,
    _MIN_WALK_VISITS,
    _V1_START,
    _V2_START,
    _first_segment,
    _followable,
    _OPDSFixtureMixin,
    _v1_links,
    _v2_links,
)


def _format(violations: dict[str, list[str]]) -> str:
    """Render a path → errors map as a readable assertion message."""
    lines = ["OPDS schema violations:"]
    for path, errors in violations.items():
        lines.append(f"  {path}")
        lines.extend(f"      - {error}" for error in errors)
    return "\n".join(lines)


class _SchemaWalkMixin(_OPDSFixtureMixin):
    """Fixture enriched with metadata, plus a feed-walking helper."""

    # pk of the one comic given a bookmark (so the progression endpoint has a
    # position to report); set in ``_enrich_comics``.
    bookmarked_pk: int = 0

    @override
    def setUp(self) -> None:
        """Attach rich metadata so feeds exercise the heavy code paths."""
        super().setUp()
        self._enrich_comics()

    def _enrich_comics(self) -> None:
        """
        Give every comic credits, tags, an arc, an identifier, language, etc.

        The base fixture's comics are metadata-thin, so the feeds it produces
        never exercise contributor / subject / belongs-to / alternate-link /
        reading-direction emission — exactly where schema violations hide.
        Shared metadata objects are attached to every comic (M2M) to avoid
        unique-constraint churn; reading directions are varied to exercise both
        branches of the layout/progression mapping. One comic also gets a
        bookmark so the progression endpoint returns a document to validate.
        """
        writer = Credit.objects.create(
            person=CreditPerson.objects.create(name="Jane Writer"),
            role=CreditRole.objects.create(name="Writer"),
        )
        colorist = Credit.objects.create(
            person=CreditPerson.objects.create(name="Cole Orist"),
            role=CreditRole.objects.create(name="Colorist"),
        )
        genre = Genre.objects.create(name="Sci-Fi")
        character = Character.objects.create(name="Captain Codex")
        tag = Tag.objects.create(name="HiRes")
        team = Team.objects.create(name="The Maintainers")
        location = Location.objects.create(name="Repoville")
        series_group = SeriesGroup.objects.create(name="Crossover")
        arc_number = StoryArcNumber.objects.create(
            story_arc=StoryArc.objects.create(name="The Big Refactor"), number=1
        )
        identifier = Identifier.objects.create(
            source=IdentifierSource.objects.create(name="comicvine"),
            id_type=IdentifierType.ISSUE.value,
            key="codex-1",
            url="https://comicvine.example.com/issue/codex-1",
        )
        language = Language.objects.create(name="en")

        directions = ("ltr", "rtl", "ttb", "btt")
        for idx, comic in enumerate(Comic.objects.all()):
            comic.credits.add(writer, colorist)
            comic.genres.add(genre)
            comic.characters.add(character)
            comic.tags.add(tag)
            comic.teams.add(team)
            comic.locations.add(location)
            comic.series_groups.add(series_group)
            comic.story_arc_numbers.add(arc_number)
            comic.identifiers.add(identifier)
            comic.language = language
            comic.reading_direction = directions[idx % len(directions)]
            comic.save()

        # One bookmark so the progression endpoint has a position to report.
        first = Comic.objects.order_by("pk").first()
        if first:
            self.bookmarked_pk = first.pk
            Bookmark.objects.create(user=self.user, comic=first, page=0)

        # Browser feeds go through cachalot; clear so the enriched rows surface.
        cache.clear()

    def _iter_feeds(
        self, start: str, parse: Callable[[Any], list[tuple[str | None, str]]]
    ) -> Iterator[tuple[str, Any]]:
        """Yield ``(path, response)`` for every followable feed from ``start``."""
        seen: set[str] = set()
        queue: deque[str] = deque([start])
        while queue and len(seen) < _MAX_VISITS:
            path = queue.popleft()
            if path in seen:
                continue
            seen.add(path)
            response = self.client.get(path)
            yield path, response
            if response.status_code != _HTTP_OK:
                continue
            for _rel, href in parse(response):
                follow = _followable(href, start)
                if follow and follow not in seen:
                    queue.append(follow)


class OPDSv2SchemaTestCase(_SchemaWalkMixin, TestCase):
    """OPDS 2.0 (JSON) schema compliance."""

    def test_feeds_schema_compliant(self) -> None:
        """Every emitted v2 feed validates; manifests validate as webpub."""
        violations: dict[str, list[str]] = {}
        feeds = manifests = 0
        for path, response in self._iter_feeds(
            _V2_START, lambda r: _v2_links(r.json())
        ):
            if response.status_code != _HTTP_OK:
                continue
            data = response.json()
            if _first_segment(path, _V2_START) == "c":
                manifests += 1
                errors = validate_opds2_manifest(data)
            else:
                feeds += 1
                errors = validate_opds2_feed(data)
            # #43: the `authenticate` link property may appear on any response.
            errors += validate_v2_authenticate(data)
            if errors:
                violations[path] = errors
        assert feeds > _MIN_WALK_VISITS, "walk did not traverse the v2 catalog"
        assert manifests > 0, "walk never reached a publication manifest"
        assert not violations, _format(violations)

    def test_manifest_schema_compliant(self) -> None:
        """The manifest validates against webpub-manifest + the DiViNa profile."""
        pk = self.bookmarked_pk or Comic.objects.values_list("pk", flat=True).first()
        url = f"{_V2_START}c/{pk}/1"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        data = response.json()
        errors = validate_opds2_manifest(data) + validate_divina_profile(data)
        assert not errors, _format({url: errors})

    def test_progression_document_compliant(self) -> None:
        """The progression endpoint returns a valid OPDS Progression 1.0 doc."""
        url = f"{_V2_START}comics/{self.bookmarked_pk}/position"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        errors = validate_opds_progression(response.json())
        assert not errors, _format({url: errors})

    def test_authentication_document_compliant(self) -> None:
        """The OPDS Authentication Document validates against the 1.0 schema."""
        url = reverse("opds:auth:v1")
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        errors = validate_opds_authentication(response.json())
        assert not errors, _format({url: errors})

    def test_unauthorized_returns_auth_document(self) -> None:
        """
        A bad credential yields 401 + a valid OPDS Authentication Document.

        Strict clients (e.g. Stump) treat the auth challenge as OPDS and reject
        it if malformed — notably the ``id`` must be an absolute URI, not a
        relative path. Uses a fresh unauthenticated client with a bogus bearer
        token so authentication is attempted and fails.
        """
        response = Client().get(_V2_START, HTTP_AUTHORIZATION="Bearer deadbeef")
        assert response.status_code == HTTPStatus.UNAUTHORIZED, response.content
        assert response.headers["Content-Type"].startswith(MimeType.AUTHENTICATION)
        assert response.headers.get("WWW-Authenticate"), "401 needs WWW-Authenticate"
        data = response.json()
        errors = validate_opds_authentication(data)
        assert not errors, _format({_V2_START: errors})
        parsed = urlparse(data["id"])
        not_absolute = f"auth id not absolute: {data['id']!r}"
        assert parsed.scheme, not_absolute
        assert parsed.netloc, not_absolute

    def test_validators_reject_malformed(self) -> None:
        """A no-op validator can't pass silently — broken docs must error."""
        assert validate_opds2_feed({"metadata": {}})
        assert validate_opds2_manifest({"metadata": {}})
        assert validate_opds_progression({"device": {}})
        assert validate_opds_authentication({"title": "x"})


class OPDSv1SchemaTestCase(_SchemaWalkMixin, TestCase):
    """OPDS 1.2 (Atom XML) schema compliance."""

    def test_feeds_schema_compliant(self) -> None:
        """Every emitted v1.2 Atom feed validates against the OPDS RELAX NG."""
        violations: dict[str, list[str]] = {}
        feeds = 0
        for path, response in self._iter_feeds(
            _V1_START, lambda r: _v1_links(r.content)
        ):
            if response.status_code != _HTTP_OK:
                continue
            feeds += 1
            # Structural OPDS 1.2 + strict Page Streaming Extension checks.
            errors = validate_opds1(response.content)
            errors += validate_opds_pse(response.content)
            if errors:
                violations[path] = errors
        assert feeds > _MIN_WALK_VISITS, "walk did not traverse the v1.2 catalog"
        assert not violations, _format(violations)

    def _stream_last_read_by_pk(self) -> dict[int, str | None]:
        """Walk the v1.2 catalog, mapping comic pk -> its PSE ``lastRead``."""
        atom_link = "{http://www.w3.org/2005/Atom}link"
        pse_last_read = "{http://vaemendis.net/opds-pse/ns}lastRead"
        last_read_by_pk: dict[int, str | None] = {}
        for _path, response in self._iter_feeds(
            _V1_START, lambda r: _v1_links(r.content)
        ):
            if response.status_code != _HTTP_OK:
                continue
            root = ET.fromstring(response.content)  # noqa: S314
            for link in root.iter(atom_link):
                if link.get("rel") != Rel.STREAM:
                    continue
                match = re.search(r"/c/(\d+)/", link.get("href", ""))
                assert match, f"stream link href has no pk: {link.get('href')!r}"
                last_read_by_pk[int(match.group(1))] = link.get(pse_last_read)
        return last_read_by_pk

    def test_pse_last_read_is_one_indexed(self) -> None:
        """
        PSE ``lastRead`` is 1-indexed where Codex's bookmark page is 0-indexed.

        A 0-indexed page-N bookmark surfaces as ``pse:lastRead="N+1"``; an
        unbookmarked comic emits none. The fixture bookmarks
        ``self.bookmarked_pk`` on page 0 — the boundary that emitted nothing
        pre-fix (0 is falsy in the template). A second bookmark on a non-zero
        page pins the general N -> N+1 mapping. Schema validation alone can't
        catch the off-by-one (any positive integer passes), so this asserts the
        exact emitted values. Unbookmarked comics (``page`` annotated 0 via
        ``Sum(default=0)``, no bookmark) must stay silent — guarding on ``page``
        alone would wrongly tag every unread comic ``lastRead="1"``.
        """
        # Second bookmark on a non-zero page; bump page_count so the page is in
        # range and lazy_metadata stays short-circuited (page_count+file_type).
        other = Comic.objects.exclude(pk=self.bookmarked_pk).order_by("pk").first()
        assert other is not None
        Comic.objects.filter(pk=other.pk).update(page_count=10)
        Bookmark.objects.create(user=self.user, comic=other, page=2)
        cache.clear()  # browser feeds are cachalot-cached

        last_read_by_pk = self._stream_last_read_by_pk()

        assert last_read_by_pk, "walk surfaced no PSE stream links"
        # 0-indexed page 0 -> 1-indexed "1" (absent pre-fix); page 2 -> "3".
        assert last_read_by_pk.get(self.bookmarked_pk) == "1"
        assert last_read_by_pk.get(other.pk) == "3"
        # Unbookmarked comics omit lastRead entirely.
        unread = {
            pk: lr
            for pk, lr in last_read_by_pk.items()
            if pk not in {self.bookmarked_pk, other.pk}
        }
        assert unread, "walk surfaced no unbookmarked comic stream links"
        assert all(lr is None for lr in unread.values()), (
            f"unbookmarked comics must omit pse:lastRead, got {unread}"
        )

    def test_opensearch_document_compliant(self) -> None:
        """The OpenSearch description document validates against the 1.1 grammar."""
        url = reverse("opds:v1:opensearch_v1")
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        # Served under the spec's media type, matching the feed's search link.
        assert response.headers["Content-Type"].startswith(MimeType.OPENSEARCH)
        errors = validate_opensearch(response.content)
        assert not errors, _format({url: errors})

    def test_validators_reject_malformed(self) -> None:
        """The RELAX NG validators must reject malformed documents."""
        assert validate_opds1(b'<wrong xmlns="http://www.w3.org/2005/Atom"/>')
        bad_pse = (
            b'<feed xmlns="http://www.w3.org/2005/Atom"'
            b' xmlns:pse="http://vaemendis.net/opds-pse/ns"><entry>'
            b'<link rel="http://vaemendis.net/opds-pse/stream" type="image/webp"'
            b' href="/s" pse:count="x"/></entry></feed>'
        )
        assert validate_opds_pse(bad_pse)
        # OpenSearch doc missing the required ShortName.
        bad_opensearch = (
            b'<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">'
            b"<Description>d</Description>"
            b'<Url type="text/html" template="/s?q={searchTerms}"/>'
            b"</OpenSearchDescription>"
        )
        assert validate_opensearch(bad_opensearch)

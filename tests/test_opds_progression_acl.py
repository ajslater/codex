"""
The OPDS Progression endpoint is not an existence oracle.

``GET /opds/v2.0/comics/<pk>/position`` has always gone through the ACL
seam, but the ``PUT`` resolved ``page_count`` off an unfiltered
``Comic.objects.filter(pk=...)``. The ``None`` return becomes a 404 and
anything else a 200, so an unauthenticated-for-this-library caller could
walk the pk space and learn exactly which comics exist -- and the write
itself landed on the bookmark queue with the raw URL pk.

The relaxation that survives is deliberate and pinned here too: the
pending-delete half of the ACL stays off for the write, so a position
recorded while the file is away still lands. Writes land, reads hide.
"""

import base64
import json
import shutil
from pathlib import Path
from typing import Final, override

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token

from codex.choices.admin import AdminFlagChoices
from codex.models import (
    AdminFlag,
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.auth import GroupAuth
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_PROGRESSION_MIME: Final = "application/opds-progression+json"
_TMP_DIR: Final = tmp_dir("codex.tests.progression_acl")
_OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
_HTTP_UNAUTHORIZED: Final = 401
_HTTP_NOT_FOUND: Final = 404
_PAGE_COUNT: Final = 11
#: 0.5 over a 0..10 page span.
_MID_PAGE: Final = 5
_MID_PROGRESSION: Final = 0.5


def _basic(username: str, password: str) -> str:
    """Build a Basic ``Authorization`` header value."""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def _assert_no_position(response) -> None:
    """
    "No position" is 200 with an empty payload, per OPDS Progression 1.0.

    The draft's only GET success row is ``200 OK | Progression Document
    or an empty payload``; it defines no 204.
    """
    assert response.status_code == _HTTP_OK, response.status_code
    assert response.content == b"", response.content
    assert "Content-Type" not in response.headers, response.headers
    assert response.headers["Content-Length"] == "0", response.headers


class ProgressionSeedTestCase(TestCase):
    """
    Shared fixture: one visible comic, one behind a group.

    Carries no tests of its own. The identity under test is the only
    thing that varies between the two cases below, so it is the only
    thing they override -- inheriting the tests instead would run the
    logged-in assertions against an anonymous client.
    """

    @override
    def setUp(self) -> None:
        """Seed a visible comic and one behind a group the user isn't in."""
        cache.clear()
        init_admin_flags()
        for path in (_OPEN_DIR, _PRIVATE_DIR):
            path.mkdir(exist_ok=True, parents=True)

        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        self.groups = (  # pyright: ignore[reportUninitializedInstanceVariable]
            publisher,
            imprint,
            series,
            Volume.objects.create(
                name="2024", series=series, imprint=imprint, publisher=publisher
            ),
        )

        self.comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            Library.objects.create(path=str(_OPEN_DIR)), _OPEN_DIR, "open"
        )

        private_library = Library.objects.create(path=str(_PRIVATE_DIR))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            private_library, _PRIVATE_DIR, "private"
        )

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="progression", password=_TEST_PASSWORD
        )
        self.client = Client()

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _make_comic(self, library, dir_path: Path, name: str) -> Comic:
        """Create a Comic row backed by a touch file."""
        path = dir_path / f"{name}.cbz"
        path.touch()
        publisher, imprint, series, volume = self.groups
        return Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name=name,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            page_count=_PAGE_COUNT,
            size=42,
        )

    @staticmethod
    def _url(comic) -> str:
        return f"/opds/v2.0/comics/{comic.pk}/position"

    def _put(self, comic, progression: float = 0.5):
        return self.client.put(
            self._url(comic),
            data=json.dumps({"progression": progression}),
            content_type=_PROGRESSION_MIME,
        )

    @staticmethod
    def _stored_pages() -> list[tuple[int, int]]:
        return list(Bookmark.objects.values_list("comic_id", "page"))


class OPDS2ProgressionACLTestCase(ProgressionSeedTestCase):
    """Both verbs answer the same way for a comic the caller can't reach."""

    @override
    def setUp(self) -> None:
        """Seed the fixture, then take the user's identity."""
        super().setUp()
        self.client.force_login(self.user)

    def test_a_reachable_comic_accepts_the_position(self) -> None:
        """The baseline the ACL must not break."""
        assert self._put(self.comic).status_code == _HTTP_OK
        assert self._stored_pages() == [(self.comic.pk, _MID_PAGE)]

    def test_an_unreachable_comic_is_not_written(self) -> None:
        """A PUT to a library the caller can't browse is a 404, not a write."""
        assert self._put(self.private_comic).status_code == _HTTP_NOT_FOUND
        assert not self._stored_pages()

    def test_the_put_does_not_leak_existence(self) -> None:
        """
        A real private comic and a pk that was never used answer alike.

        That identity is the whole point: any divergence is the oracle.
        """
        missing_pk = Comic.objects.order_by("-pk").values_list("pk", flat=True)[0] + 100
        real = self._put(self.private_comic)
        fake = self.client.put(
            f"/opds/v2.0/comics/{missing_pk}/position",
            data=json.dumps({"progression": 0.5}),
            content_type=_PROGRESSION_MIME,
        )
        assert real.status_code == fake.status_code == _HTTP_NOT_FOUND

    def test_the_get_hides_an_unreachable_comic(self) -> None:
        """The read half of the same seam, for contrast with the write."""
        _assert_no_position(self.client.get(self._url(self.comic)))
        assert (
            self.client.get(self._url(self.private_comic)).status_code
            == _HTTP_NOT_FOUND
        )

    def test_a_stamped_comic_still_accepts_the_position(self) -> None:
        """
        ``include_missing=True`` survives the fix.

        A comic whose file went away is hidden from listings for the
        retention window but must still record where the reader got to,
        or the position is lost exactly when it matters most.
        """
        Comic.objects.filter(pk=self.comic.pk).update(missing_since=timezone.now())
        assert self._put(self.comic).status_code == _HTTP_OK
        assert self._stored_pages() == [(self.comic.pk, _MID_PAGE)]

    def test_a_stamped_comic_hides_the_position_it_accepted(self) -> None:
        """
        The other half of "writes land, reads hide", with a live bookmark.

        A stamped comic and its bookmarks are visible to nobody -- not
        even to staff -- outside the admin Pending Deletes panel, so the
        read 404s for the retention window even though the write above
        was accepted. The asymmetry is the point: the position is not
        discarded, it is just not readable until the row comes back.
        """
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_MID_PAGE)
        Comic.objects.filter(pk=self.comic.pk).update(missing_since=timezone.now())
        assert self.client.get(self._url(self.comic)).status_code == _HTTP_NOT_FOUND

    def test_a_reachable_comic_reads_its_position_back(self) -> None:
        """The plain 200 path, which nothing in this module pinned."""
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_MID_PAGE)
        response = self.client.get(self._url(self.comic))
        assert response.status_code == _HTTP_OK
        assert response.json()["progression"] == _MID_PROGRESSION

    def test_a_reachable_comic_without_a_position_has_an_empty_payload(self) -> None:
        """Never opened is 200 + empty payload, not 204 and not a zeroed document."""
        _assert_no_position(self.client.get(self._url(self.comic)))

    def test_put_with_invalid_progression_is_a_400_not_a_redirect(self) -> None:
        """
        A schema-invalid document surfaces as 400.

        The OPDS error handler used to test for a ``progression`` path
        suffix the route never had, so this redirected to the start feed.
        """
        response = self.client.put(
            self._url(self.comic),
            data=json.dumps({"progression": "abc"}),
            content_type=_PROGRESSION_MIME,
        )
        assert response.status_code == _HTTP_BAD_REQUEST, response.status_code


class OPDS2ProgressionCredentialsTestCase(ProgressionSeedTestCase):
    """Header-credentialed clients, as real OPDS readers send them."""

    def test_basic_auth_reads_a_position_end_to_end(self) -> None:
        """Basic resolves the user; no row is the empty 200; a bad password is 401."""
        auth = _basic(self.user.username, _TEST_PASSWORD)
        _assert_no_position(
            self.client.get(self._url(self.comic), HTTP_AUTHORIZATION=auth)
        )
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_MID_PAGE)
        response = self.client.get(self._url(self.comic), HTTP_AUTHORIZATION=auth)
        assert response.status_code == _HTTP_OK
        assert response.json()["progression"] == _MID_PROGRESSION
        bad = _basic(self.user.username, "wrong")
        response = Client().get(self._url(self.comic), HTTP_AUTHORIZATION=bad)
        assert response.status_code == _HTTP_UNAUTHORIZED

    def test_bearer_auth_reads_a_position_end_to_end(self) -> None:
        """The token keyword is ``Bearer``, not DRF's default ``Token``."""
        token = Token.objects.create(user=self.user)
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_MID_PAGE)
        response = self.client.get(
            self._url(self.comic), HTTP_AUTHORIZATION=f"Bearer {token.key}"
        )
        assert response.status_code == _HTTP_OK
        assert response.json()["progression"] == _MID_PROGRESSION

    def test_position_requires_credentials_when_non_users_is_off(self) -> None:
        """With anonymous browsing off, an uncredentialed GET is challenged."""
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=False)
        cache.clear()
        response = self.client.get(self._url(self.comic))
        assert response.status_code == _HTTP_UNAUTHORIZED
        assert response.headers["WWW-Authenticate"].startswith("Basic realm=")
        auth = _basic(self.user.username, _TEST_PASSWORD)
        _assert_no_position(
            self.client.get(self._url(self.comic), HTTP_AUTHORIZATION=auth)
        )

    def test_a_cookie_only_position_get_after_a_basic_feed_get_is_anonymous(
        self,
    ) -> None:
        """
        The session cookie a feed GET sets carries no user.

        A client that sends Basic on feeds but only replays the cookie
        on position requests asks as a different reader.
        """
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_MID_PAGE)
        auth = _basic(self.user.username, _TEST_PASSWORD)
        assert self.client.get("/opds/v2.0/", HTTP_AUTHORIZATION=auth).status_code == (
            _HTTP_OK
        )
        assert settings.SESSION_COOKIE_NAME in self.client.cookies
        _assert_no_position(self.client.get(self._url(self.comic)))
        response = self.client.get(self._url(self.comic), HTTP_AUTHORIZATION=auth)
        assert response.status_code == _HTTP_OK
        assert response.json()["progression"] == _MID_PROGRESSION


class OPDS2ProgressionAnonTestCase(ProgressionSeedTestCase):
    """
    The position endpoint for visitors who never established a session.

    Most OPDS clients send neither credentials nor a session cookie on a
    position request. The never-match bookmark filter that identity gets
    lands in a ``FilteredRelation`` join condition here, so it has to
    compile to a real SQL predicate; an ``EmptyResultSet`` there takes
    the whole query with it and every pk answers 404.
    """

    def _establish_session(self) -> str:
        """Give the client a real session cookie, as a write would."""
        session = self.client.session
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
        return session.session_key

    def test_a_sessionless_visitor_gets_no_position(self) -> None:
        """No identity, no bookmark -- but the comic is still there."""
        _assert_no_position(self.client.get(self._url(self.comic)))

    def test_a_session_visitor_with_no_bookmark_gets_no_position(self) -> None:
        """The same answer once a session exists, for contrast."""
        self._establish_session()
        _assert_no_position(self.client.get(self._url(self.comic)))

    def test_a_session_visitor_reads_their_own_position_back(self) -> None:
        """A session-keyed bookmark is still resolved by the join."""
        session_key = self._establish_session()
        Bookmark.objects.create(
            session_id=session_key, comic=self.comic, page=_MID_PAGE
        )
        response = self.client.get(self._url(self.comic))
        assert response.status_code == _HTTP_OK
        assert response.json()["progression"] == _MID_PROGRESSION

    def test_a_sessionless_visitor_cannot_probe_a_private_comic(self) -> None:
        """The empty 200 must not come at the cost of the existence oracle."""
        assert (
            self.client.get(self._url(self.private_comic)).status_code
            == _HTTP_NOT_FOUND
        )

    def test_a_sessionless_visitor_does_not_see_another_bookmark(self) -> None:
        """
        The never-match filter still has to match nothing.

        A relation-scoped never-match that accidentally matched rows
        would hand this visitor the logged-in user's position.
        """
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_MID_PAGE)
        _assert_no_position(self.client.get(self._url(self.comic)))

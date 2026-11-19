"""
KOReader kosync progress sync.

The endpoints speak koreader-sync-server's protocol under ``/koreader/``.
What these tests pin:

* Every route 404s while the KOReader Sync flag is off.
* Credentials are the Codex username and the MD5 of one of the user's
  device keys.
  Sessions and Non Users never authenticate these views.
* A push for a comic that is unknown, or behind the library-group or
  age-rating ACL, is a 200 that stores nothing, and a pull for one is
  ``{}``: the two are indistinguishable.
* KOReader's 1-based page maps to Codex's 0-based page both ways, with a
  percentage fallback when the device counts pages differently.
"""

import json
from typing import Any, Final

from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.urls.base import set_script_prefix

from codex.choices.admin import AdminFlagChoices
from codex.models import (
    AdminFlag,
    AgeRating,
    AgeRatingMetron,
    Bookmark,
    Comic,
    ComicKoreaderHash,
)
from codex.models.auth import UserAuth
from codex.views.koreader.progress import CODEX_DEVICE_ID, map_push
from tests.koreader_fixtures import (
    ACCEPT,
    PAGE_COUNT,
    KOSyncTestCase,
    binary_hash,
    md5,
    name_hash,
    set_flag,
)
from tests.reader_fixtures import PASSWORD

_HTTP_OK: Final = 200
_HTTP_UNAUTHORIZED: Final = 401
_HTTP_PAYMENT_REQUIRED: Final = 402
_HTTP_FORBIDDEN: Final = 403
_HTTP_NOT_FOUND: Final = 404
_UNKNOWN_HASH: Final = "0" * 32
_PAGE_ONE_BASED: Final = 5
_STORED_PAGE: Final = 4
_WEB_PAGE: Final = 9
_HALF: Final = 0.5


class KOSyncFlagTestCase(KOSyncTestCase):
    """The flag gates everything."""

    def test_flag_off_is_404_everywhere(self) -> None:
        """No route answers while the flag is off, authenticated or not."""
        set_flag(on=False)
        cache.clear()
        headers = self._headers()
        responses = (
            self.client.get("/koreader/users/auth", **headers),
            self.client.post("/koreader/users/create", **headers),
            self._push(binary_hash(self.comic)),
            self._pull(binary_hash(self.comic)),
            self.client.get("/koreader/healthcheck"),
        )
        for response in responses:
            assert response.status_code == _HTTP_NOT_FOUND, response
        assert not self._bookmarks()

    def test_healthcheck(self) -> None:
        """Up, without credentials."""
        response = self.client.get("/koreader/healthcheck")
        assert response.status_code == _HTTP_OK
        assert response.json() == {"state": "OK"}

    def test_registration_is_refused(self) -> None:
        """Users are made in Codex."""
        response = self.client.post(
            "/koreader/users/create",
            data=json.dumps({"username": "x", "password": md5("y")}),
            content_type=ACCEPT,
        )
        assert response.status_code == _HTTP_PAYMENT_REQUIRED
        assert response.json() == {
            "code": 2005,
            "message": "User registration is disabled.",
        }


class KOSyncAuthTestCase(KOSyncTestCase):
    """Username plus the MD5 of a device key."""

    def test_good_credentials(self) -> None:
        """The key's MD5, as KOReader sends it, authorizes."""
        response = self.client.get("/koreader/users/auth", **self._headers())
        assert response.status_code == _HTTP_OK
        assert response.json() == {"authorized": "OK"}

    def test_bad_credentials(self) -> None:
        """Wrong key, raw key, login password, unknown user, no headers."""
        attempts: tuple[dict[str, Any], ...] = (
            self._headers(key=md5("wrong")),
            self._headers(key=self.key),
            self._headers(key=md5(PASSWORD)),
            self._headers(user="nobody"),
            {"HTTP_ACCEPT": ACCEPT},
        )
        for headers in attempts:
            response = self.client.get("/koreader/users/auth", **headers)
            assert response.status_code == _HTTP_UNAUTHORIZED, headers
            assert response.json() == {"code": 2001, "message": "Unauthorized"}

    def test_session_does_not_authenticate(self) -> None:
        """A logged-in browser session is not a kosync login."""
        self.client.force_login(self.user)
        response = self.client.get("/koreader/users/auth", HTTP_ACCEPT=ACCEPT)
        assert response.status_code == _HTTP_UNAUTHORIZED

    def test_non_users_does_not_authenticate(self) -> None:
        """The Non Users flag opens the browser, not sync."""
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=True)
        assert self._pull(binary_hash(self.comic), HTTP_ACCEPT=ACCEPT).status_code == (
            _HTTP_UNAUTHORIZED
        )

    def test_inactive_user_is_refused(self) -> None:
        """A deactivated account can't sync."""
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.client.get("/koreader/users/auth", **self._headers())
        assert response.status_code == _HTTP_UNAUTHORIZED

    def test_unauthenticated_push_is_401(self) -> None:
        """A push without credentials stores nothing."""
        response = self._push(binary_hash(self.comic), HTTP_ACCEPT=ACCEPT)
        assert response.status_code == _HTTP_UNAUTHORIZED
        assert not self._bookmarks()


class KOSyncProgressTestCase(KOSyncTestCase):
    """Push and pull."""

    def test_push_stores_the_zero_based_page(self) -> None:
        """Page 5 of 20 is stored as page 4, answered with a timestamp."""
        push = self._push(binary_hash(self.comic))
        assert push.status_code == _HTTP_OK
        body = push.json()
        assert body["document"] == binary_hash(self.comic)
        assert isinstance(body["timestamp"], int)
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]

    def test_pull_reads_back_the_one_based_page(self) -> None:
        """The pushed position pulls back as "5" with the push's timestamp."""
        timestamp = self._push(binary_hash(self.comic)).json()["timestamp"]
        pull = self._pull(binary_hash(self.comic))
        assert pull.status_code == _HTTP_OK
        assert pull.json() == {
            "document": binary_hash(self.comic),
            "percentage": _PAGE_ONE_BASED / PAGE_COUNT,
            "progress": str(_PAGE_ONE_BASED),
            "device": "Codex",
            "device_id": CODEX_DEVICE_ID,
            "timestamp": timestamp,
        }

    def test_vendor_content_type_is_accepted(self) -> None:
        """The body parses whatever its Content-Type."""
        response = self.client.put(
            "/koreader/syncs/progress",
            data=json.dumps(
                {
                    "document": binary_hash(self.comic),
                    "progress": "3",
                    "percentage": 0.15,
                    "device": "Kobo",
                }
            ),
            content_type=ACCEPT,
            **self._headers(),
        )
        assert response.status_code == _HTTP_OK
        assert self._bookmarks() == [(self.comic.pk, 2, False)]

    def test_pull_of_codex_progress(self) -> None:
        """A position read on the web pulls to the device."""
        Bookmark.objects.create(user=self.user, comic=self.comic, page=9)
        doc = self._pull(binary_hash(self.comic)).json()
        assert doc["progress"] == "10"
        assert doc["percentage"] == _HALF

    def test_last_page_finishes(self) -> None:
        """Page 20 of 20 marks the comic read."""
        self._push(binary_hash(self.comic), progress="20", percentage=1.0)
        assert self._bookmarks() == [(self.comic.pk, PAGE_COUNT - 1, True)]
        doc = self._pull(binary_hash(self.comic)).json()
        assert doc["progress"] == str(PAGE_COUNT)
        assert doc["percentage"] == 1.0

    def test_finished_without_a_page_pulls_the_last_page(self) -> None:
        """Marked read in the browser: the device jumps to the end."""
        Bookmark.objects.create(user=self.user, comic=self.comic, finished=True)
        assert self._pull(binary_hash(self.comic)).json()["progress"] == str(PAGE_COUNT)

    def test_out_of_range_page_is_clamped(self) -> None:
        """
        A page past Codex's end is the last page, read only at the device's end.

        Page 99 at 0.99 is a device counting 100 pages, one short of its
        end: rounding it onto Codex's last page must not finish the book,
        which only "mark unread" undoes.
        """
        self._push(binary_hash(self.comic), progress="99", percentage=0.99)
        assert self._bookmarks() == [(self.comic.pk, PAGE_COUNT - 1, False)]
        self._push(binary_hash(self.comic), progress="100", percentage=1.0)
        assert self._bookmarks() == [(self.comic.pk, PAGE_COUNT - 1, True)]

    def test_percentage_fallback_when_page_counts_differ(self) -> None:
        """
        The device counts 40 pages where Codex counts 20.

        Page 10 of 40 is a quarter through: page 5 of 20, stored as 4.
        """
        self._push(binary_hash(self.comic), progress="10", percentage=0.25)
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]

    def test_percentage_fallback_when_progress_is_not_a_page(self) -> None:
        """An xpointer is not a page number; use the percentage."""
        self._push(
            binary_hash(self.comic),
            progress="/body/DocFragment[3]/body/p[1]",
            percentage=0.5,
        )
        assert self._bookmarks() == [(self.comic.pk, 9, False)]

    def test_unmappable_push_is_200_and_stores_nothing(self) -> None:
        """An unreadable page and an out-of-range percentage store nothing."""
        response = self._push(binary_hash(self.comic), progress="x", percentage=5)
        assert response.status_code == _HTTP_OK
        assert not self._bookmarks()

    def _malformed_bodies(self) -> tuple[tuple[Any, int], ...]:
        good = {
            "document": binary_hash(self.comic),
            "progress": "5",
            "percentage": 0.25,
            "device": "Kobo",
        }

        def without(key: str) -> dict:
            return {k: v for k, v in good.items() if k != key}

        return (
            ({**good, "document": ""}, 2004),
            ({**good, "document": "a:b"}, 2004),
            (without("document"), 2004),
            ({**good, "percentage": "half"}, 2003),
            (without("percentage"), 2003),
            (without("progress"), 2003),
            (without("device"), 2003),
            ([good], 2003),
        )

    def test_malformed_pushes_are_403_like_the_reference(self) -> None:
        """
        koreader-sync-server answers bad fields with 403 and a code.

        2004 for a missing, empty or colon-containing document; 2003 for a
        missing or non-numeric percentage, or a missing progress or device.
        """
        cases = self._malformed_bodies()
        results = [(self._put_raw(body), code) for body, code in cases]
        assert [(r.status_code, r.json()["code"]) for r, _ in results] == [
            (_HTTP_FORBIDDEN, code) for _, code in results
        ]
        assert not self._bookmarks()

    def test_percentage_zero_is_a_value(self) -> None:
        """0 is a legal percentage, not a missing field."""
        response = self._push(binary_hash(self.comic), progress="1", percentage=0)
        assert response.status_code == _HTTP_OK
        assert self._bookmarks() == [(self.comic.pk, 0, False)]

    def test_unread_pull_is_empty(self) -> None:
        """No bookmark, or a page-0 unfinished one, is no progress."""
        assert self._pull(binary_hash(self.comic)).json() == {}
        Bookmark.objects.create(user=self.user, comic=self.comic, page=0)
        assert self._pull(binary_hash(self.comic)).json() == {}

    def test_filename_hash_matches(self) -> None:
        """Devices set to Filename matching find the same comic."""
        self._push(name_hash(self.comic))
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]
        assert self._pull(name_hash(self.comic)).json()["progress"] == "5"

    def test_a_shared_file_name_matches_nothing(self) -> None:
        """
        Filename matching fans out to nothing, not to every namesake.

        ``Series A/Volume 01.cbz`` and ``Series B/Volume 01.cbz`` share a name
        hash. A push stores nothing (finishing one book must not finish the
        other) and a pull reports no progress.
        """
        namesake = self._make_comic(self.library, "namesake")
        ComicKoreaderHash.objects.filter(comic_id=namesake.pk).update(
            name_hash=name_hash(self.comic)
        )
        Bookmark.objects.create(user=self.user, comic=namesake, page=9)
        response = self._push(
            name_hash(self.comic),
            progress=str(self.COMIC_PAGE_COUNT),
            percentage=1.0,
        )
        assert response.status_code == _HTTP_OK
        assert self._bookmarks() == [(namesake.pk, _WEB_PAGE, False)]
        assert self._pull(name_hash(self.comic)).json() == {}

    def test_a_hidden_namesake_does_not_spoil_a_unique_name(self) -> None:
        """Uniqueness counts only the comics the user can see."""
        ComicKoreaderHash.objects.filter(comic_id=self.private_comic.pk).update(
            name_hash=name_hash(self.comic)
        )
        self._push(name_hash(self.comic))
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]
        assert self._pull(name_hash(self.comic)).json()["progress"] == "5"

    def test_uncounted_pages_store_and_pull_nothing(self) -> None:
        """
        Until Codex counts the pages it can't place the device's position.

        Storing the raw page collapsed it to page 1 on the next push.
        """
        Comic.objects.filter(pk=self.comic.pk).update(page_count=0)
        assert self._push(binary_hash(self.comic)).status_code == _HTTP_OK
        assert not self._bookmarks()
        Bookmark.objects.create(user=self.user, comic=self.comic, page=3)
        assert self._pull(binary_hash(self.comic)).json() == {}

    def test_a_crafted_page_is_not_a_500(self) -> None:
        response = self._push(
            binary_hash(self.comic), progress="9" * 400, percentage=0.5
        )
        assert response.status_code == _HTTP_OK

    def test_hash_case_is_ignored(self) -> None:
        """Upper-case hex matches; the response echoes what was sent."""
        upper = str(binary_hash(self.comic)).upper()
        assert self._push(upper).json()["document"] == upper
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]
        assert self._pull(upper).json()["document"] == upper

    def test_other_users_progress_is_not_pulled(self) -> None:
        """Bookmarks are per user."""
        other = User.objects.create_user(username="other", password="x")  # noqa: S106
        Bookmark.objects.create(user=other, comic=self.comic, page=9)
        assert self._pull(binary_hash(self.comic)).json() == {}


class KOSyncACLTestCase(KOSyncTestCase):
    """Forbidden and unknown answer alike."""

    def test_unknown_document(self) -> None:
        """Push is 200 and stores nothing; pull is {}."""
        push = self._push(_UNKNOWN_HASH)
        assert push.status_code == _HTTP_OK
        assert push.json()["document"] == _UNKNOWN_HASH
        assert not self._bookmarks()
        pull = self._pull(_UNKNOWN_HASH)
        assert pull.status_code == _HTTP_OK
        assert pull.json() == {}

    def test_not_a_hash(self) -> None:
        """Anything that isn't 32 hex digits is unknown, not an error."""
        assert self._push("not-a-hash").status_code == _HTTP_OK
        assert self._pull("not-a-hash").json() == {}
        assert not self._bookmarks()

    def test_private_library_is_indistinguishable_from_unknown(self) -> None:
        """Library-group ACL: nothing stored, nothing read, same shapes."""
        Bookmark.objects.create(user=self.user, comic=self.private_comic, page=9)
        push = self._push(binary_hash(self.private_comic))
        unknown = self._push(_UNKNOWN_HASH)
        assert push.status_code == unknown.status_code == _HTTP_OK
        assert set(push.json()) == set(unknown.json())
        assert Bookmark.objects.get(comic=self.private_comic).page == _WEB_PAGE
        assert self._pull(binary_hash(self.private_comic)).json() == {}

    def test_age_rating_ceiling(self) -> None:
        """A comic above the user's age-rating ceiling is invisible to sync."""
        rating = AgeRating(name=MetronAgeRatingEnum.ADULT.value)
        rating.presave()
        rating.save()
        adult = self._make_comic(self.library, "adult", age_rating=rating)
        teen = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        UserAuth.objects.filter(user=self.user).update(age_rating_metron=teen)
        cache.clear()
        assert self._push(binary_hash(adult)).status_code == _HTTP_OK
        assert not Bookmark.objects.filter(comic=adult).exists()
        Bookmark.objects.create(user=self.user, comic=adult, page=9)
        assert self._pull(binary_hash(adult)).json() == {}

    def test_duplicate_hashes(self) -> None:
        """
        Two visible copies of one file share a hash.

        A push updates both; a pull returns the newer bookmark.
        """
        twin = self._make_comic(self.library, "twin")
        ComicKoreaderHash.objects.filter(comic_id=twin.pk).update(
            binary_hash=binary_hash(self.comic)
        )
        self._push(binary_hash(self.comic))
        assert self._bookmarks() == [
            (self.comic.pk, _STORED_PAGE, False),
            (twin.pk, _STORED_PAGE, False),
        ]
        Bookmark.objects.filter(comic=twin).update(page=14)
        Bookmark.objects.filter(comic=self.comic).update(
            updated_at=Bookmark.objects.get(comic=twin).updated_at.replace(year=2000)
        )
        assert self._pull(binary_hash(self.comic)).json()["progress"] == "15"


class KOSyncMappingTestCase(TestCase):
    """The page mapping on its own."""

    def test_map_push(self) -> None:
        """1-based device pages, clamped, with the percentage fallback."""
        cases = (
            (("1", 0.05, 20), (0, False)),
            (("20", 1.0, 20), (19, True)),
            ((7, 0.35, 20), (6, False)),
            (("0", 0.0, 20), (0, False)),
            (("10", 0.25, 20), (4, False)),  # device counts 40 pages
            # The fallback rounds; only the device's own end is finished.
            (("x", 0.999, 20), (19, False)),
            (("98", 0.98, 20), (19, False)),  # device counts 100 pages
            (("x", 1.0, 20), (19, True)),
            (("x", None, 20), None),
            (("3", None, 0), None),  # Codex hasn't counted pages yet
            (("3", 0.5, 0), None),
            ((None, 0.5, 0), None),
            (("3", "0.15", 20), (2, False)),
            (("3", 1.5, 20), (2, False)),  # out-of-range percentage ignored
            # A page no comic has is not a page: fall back to the percentage.
            (("9" * 400, 0.5, 20), (9, False)),
            ((10**6, 0.5, 20), (9, False)),
            (("-5", 0.5, 20), (9, False)),
        )
        for args, expected in cases:
            assert map_push(*args) == expected, args


class KOSyncURLPrefixTestCase(TestCase):
    """``reverse()`` carries ``server.url_path_prefix``."""

    def test_reverse_under_a_prefix(self) -> None:
        """The server URL a user types is origin + prefix + /koreader."""
        set_script_prefix("/codex/")
        try:
            assert reverse("koreader:users_auth") == "/codex/koreader/users/auth"
            assert (
                reverse("koreader:progress_get", kwargs={"document": _UNKNOWN_HASH})
                == f"/codex/koreader/syncs/progress/{_UNKNOWN_HASH}"
            )
        finally:
            set_script_prefix("/")

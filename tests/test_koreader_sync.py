"""
KOReader kosync progress sync.

The endpoints speak koreader-sync-server's protocol under ``/koreader/``.
What these tests pin:

* Every route 404s while the KOReader Sync flag is off.
* Credentials are the Codex username and the MD5 of the user's API token.
  Sessions and Non Users never authenticate these views.
* A push for a comic that is unknown, or behind the library-group or
  age-rating ACL, is a 200 that stores nothing, and a pull for one is
  ``{}``: the two are indistinguishable.
* KOReader's 1-based page maps to Codex's 0-based page both ways, with a
  percentage fallback when the device counts pages differently.
"""

import hashlib
import json
import shutil
from multiprocessing import Event
from pathlib import Path
from threading import Lock
from typing import Any, Final, override
from unittest.mock import patch

from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.urls.base import set_script_prefix
from loguru import logger
from rest_framework.authtoken.models import Token

from codex.choices.admin import AdminFlagChoices
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.librarian.scribe.janitor.tasks import JanitorKoreaderHashTask
from codex.librarian.scribe.koreader_hash import (
    koreader_name_md5,
    koreader_partial_md5,
)
from codex.models import (
    AdminFlag,
    AgeRating,
    AgeRatingMetron,
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.auth import GroupAuth, UserAuth
from codex.startup import init_admin_flags
from codex.views.koreader.progress import CODEX_DEVICE_ID, map_push
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.koreader_sync")
_OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"
_ACCEPT: Final = "application/vnd.koreader.v1+json"
_PAGE_COUNT: Final = 20
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


def _md5(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def _set_flag(*, on: bool) -> None:
    AdminFlag.objects.filter(key=AdminFlagChoices.KOREADER_SYNC.value).update(on=on)


class KOSyncTestCase(TestCase):
    """Fixture: an open comic, a private one and a user with a token."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _set_flag(on=True)
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
        self.library = Library.objects.create(path=str(_OPEN_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = self._make_comic(self.library, _OPEN_DIR, "open")  # pyright: ignore[reportUninitializedInstanceVariable]

        private_library = Library.objects.create(path=str(_PRIVATE_DIR))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            private_library, _PRIVATE_DIR, "private"
        )

        self.user = User.objects.create_user(username="reader", password="x")  # noqa: S106 # pyright: ignore[reportUninitializedInstanceVariable]
        self.token = Token.objects.create(user=self.user)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _make_comic(self, library, dir_path: Path, name: str, **kwargs) -> Comic:
        path = dir_path / f"{name}.cbz"
        path.write_bytes(name.encode() * 300)
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
            **kwargs,
        )

    def _headers(self, user: str | None = None, key: str | None = None) -> dict:
        return {
            "HTTP_ACCEPT": _ACCEPT,
            "HTTP_X_AUTH_USER": user if user is not None else self.user.username,
            "HTTP_X_AUTH_KEY": key if key is not None else _md5(self.token.key),
        }

    def _push(
        self,
        document: str | None,
        progress: str | None = "5",
        percentage: float | None = 0.25,
        **headers: Any,
    ):
        body = {
            "document": document,
            "progress": progress,
            "percentage": percentage,
            "device": "Kobo",
            "device_id": "ABC",
        }
        return self.client.put(
            "/koreader/syncs/progress",
            data=json.dumps(body),
            content_type="application/json",
            **(headers or self._headers()),
        )

    def _put_raw(self, body):
        return self.client.put(
            "/koreader/syncs/progress",
            data=json.dumps(body),
            content_type="application/json",
            **self._headers(),
        )

    def _pull(self, document: str | None, **headers: Any):
        return self.client.get(
            f"/koreader/syncs/progress/{document}", **(headers or self._headers())
        )

    def _bookmarks(self) -> list[tuple[int, int | None, bool]]:
        return list(
            Bookmark.objects.order_by("comic_id").values_list(
                "comic_id", "page", "finished"
            )
        )


class KOSyncHashTestCase(KOSyncTestCase):
    """Comics get both hashes when saved."""

    def test_presave_sets_both_hashes(self) -> None:
        """The binary and the filename hash match the file."""
        assert self.comic.koreader_hash == koreader_partial_md5(self.comic.path)
        assert self.comic.koreader_name_hash == koreader_name_md5(self.comic.path)

    def test_unreadable_file_leaves_the_binary_hash_null(self) -> None:
        """A file that can't be read doesn't fail the save."""
        comic = Comic.objects.get(pk=self.comic.pk)
        comic.path = str(_OPEN_DIR)  # a directory: stat works, open fails
        comic.set_koreader_hashes()
        assert comic.koreader_hash is None
        assert comic.koreader_name_hash == koreader_name_md5(_OPEN_DIR)


class KOSyncFlagTestCase(KOSyncTestCase):
    """The flag gates everything."""

    def test_flag_off_is_404_everywhere(self) -> None:
        """No route answers while the flag is off, authenticated or not."""
        _set_flag(on=False)
        cache.clear()
        headers = self._headers()
        responses = (
            self.client.get("/koreader/users/auth", **headers),
            self.client.post("/koreader/users/create", **headers),
            self._push(self.comic.koreader_hash),
            self._pull(self.comic.koreader_hash),
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
            data=json.dumps({"username": "x", "password": _md5("y")}),
            content_type=_ACCEPT,
        )
        assert response.status_code == _HTTP_PAYMENT_REQUIRED
        assert response.json() == {
            "code": 2005,
            "message": "User registration is disabled.",
        }


class KOSyncAuthTestCase(KOSyncTestCase):
    """Username plus the MD5 of the API token."""

    def test_good_credentials(self) -> None:
        """The token's MD5, as KOReader sends it, authorizes."""
        response = self.client.get("/koreader/users/auth", **self._headers())
        assert response.status_code == _HTTP_OK
        assert response.json() == {"authorized": "OK"}

    def test_bad_credentials(self) -> None:
        """Wrong key, raw token, login password, unknown user, no headers."""
        attempts: tuple[dict[str, Any], ...] = (
            self._headers(key=_md5("wrong")),
            self._headers(key=self.token.key),
            self._headers(key=_md5("x")),
            self._headers(user="nobody"),
            {"HTTP_ACCEPT": _ACCEPT},
        )
        for headers in attempts:
            response = self.client.get("/koreader/users/auth", **headers)
            assert response.status_code == _HTTP_UNAUTHORIZED, headers
            assert response.json() == {"code": 2001, "message": "Unauthorized"}

    def test_session_does_not_authenticate(self) -> None:
        """A logged-in browser session is not a kosync login."""
        self.client.force_login(self.user)
        response = self.client.get("/koreader/users/auth", HTTP_ACCEPT=_ACCEPT)
        assert response.status_code == _HTTP_UNAUTHORIZED

    def test_non_users_does_not_authenticate(self) -> None:
        """The Non Users flag opens the browser, not sync."""
        AdminFlag.objects.filter(key=AdminFlagChoices.NON_USERS.value).update(on=True)
        assert self._pull(
            self.comic.koreader_hash, HTTP_ACCEPT=_ACCEPT
        ).status_code == (_HTTP_UNAUTHORIZED)

    def test_inactive_user_is_refused(self) -> None:
        """A deactivated account can't sync."""
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.client.get("/koreader/users/auth", **self._headers())
        assert response.status_code == _HTTP_UNAUTHORIZED

    def test_unauthenticated_push_is_401(self) -> None:
        """A push without credentials stores nothing."""
        response = self._push(self.comic.koreader_hash, HTTP_ACCEPT=_ACCEPT)
        assert response.status_code == _HTTP_UNAUTHORIZED
        assert not self._bookmarks()


class KOSyncProgressTestCase(KOSyncTestCase):
    """Push and pull."""

    def test_push_stores_the_zero_based_page(self) -> None:
        """Page 5 of 20 is stored as page 4, answered with a timestamp."""
        push = self._push(self.comic.koreader_hash)
        assert push.status_code == _HTTP_OK
        body = push.json()
        assert body["document"] == self.comic.koreader_hash
        assert isinstance(body["timestamp"], int)
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]

    def test_pull_reads_back_the_one_based_page(self) -> None:
        """The pushed position pulls back as "5" with the push's timestamp."""
        timestamp = self._push(self.comic.koreader_hash).json()["timestamp"]
        pull = self._pull(self.comic.koreader_hash)
        assert pull.status_code == _HTTP_OK
        assert pull.json() == {
            "document": self.comic.koreader_hash,
            "percentage": _PAGE_ONE_BASED / _PAGE_COUNT,
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
                    "document": self.comic.koreader_hash,
                    "progress": "3",
                    "percentage": 0.15,
                    "device": "Kobo",
                }
            ),
            content_type=_ACCEPT,
            **self._headers(),
        )
        assert response.status_code == _HTTP_OK
        assert self._bookmarks() == [(self.comic.pk, 2, False)]

    def test_pull_of_codex_progress(self) -> None:
        """A position read on the web pulls to the device."""
        Bookmark.objects.create(user=self.user, comic=self.comic, page=9)
        doc = self._pull(self.comic.koreader_hash).json()
        assert doc["progress"] == "10"
        assert doc["percentage"] == _HALF

    def test_last_page_finishes(self) -> None:
        """Page 20 of 20 marks the comic read."""
        self._push(self.comic.koreader_hash, progress="20", percentage=1.0)
        assert self._bookmarks() == [(self.comic.pk, _PAGE_COUNT - 1, True)]
        doc = self._pull(self.comic.koreader_hash).json()
        assert doc["progress"] == str(_PAGE_COUNT)
        assert doc["percentage"] == 1.0

    def test_finished_without_a_page_pulls_the_last_page(self) -> None:
        """Marked read in the browser: the device jumps to the end."""
        Bookmark.objects.create(user=self.user, comic=self.comic, finished=True)
        assert self._pull(self.comic.koreader_hash).json()["progress"] == str(
            _PAGE_COUNT
        )

    def test_out_of_range_page_is_clamped(self) -> None:
        """A page past the end is the last page, and read."""
        self._push(self.comic.koreader_hash, progress="99", percentage=0.99)
        assert self._bookmarks() == [(self.comic.pk, _PAGE_COUNT - 1, True)]

    def test_percentage_fallback_when_page_counts_differ(self) -> None:
        """
        The device counts 40 pages where Codex counts 20.

        Page 10 of 40 is a quarter through: page 5 of 20, stored as 4.
        """
        self._push(self.comic.koreader_hash, progress="10", percentage=0.25)
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]

    def test_percentage_fallback_when_progress_is_not_a_page(self) -> None:
        """An xpointer is not a page number; use the percentage."""
        self._push(
            self.comic.koreader_hash,
            progress="/body/DocFragment[3]/body/p[1]",
            percentage=0.5,
        )
        assert self._bookmarks() == [(self.comic.pk, 9, False)]

    def test_unmappable_push_is_200_and_stores_nothing(self) -> None:
        """An unreadable page and an out-of-range percentage store nothing."""
        response = self._push(self.comic.koreader_hash, progress="x", percentage=5)
        assert response.status_code == _HTTP_OK
        assert not self._bookmarks()

    def _malformed_bodies(self) -> tuple[tuple[Any, int], ...]:
        good = {
            "document": self.comic.koreader_hash,
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
        response = self._push(self.comic.koreader_hash, progress="1", percentage=0)
        assert response.status_code == _HTTP_OK
        assert self._bookmarks() == [(self.comic.pk, 0, False)]

    def test_unread_pull_is_empty(self) -> None:
        """No bookmark, or a page-0 unfinished one, is no progress."""
        assert self._pull(self.comic.koreader_hash).json() == {}
        Bookmark.objects.create(user=self.user, comic=self.comic, page=0)
        assert self._pull(self.comic.koreader_hash).json() == {}

    def test_filename_hash_matches(self) -> None:
        """Devices set to Filename matching find the same comic."""
        self._push(self.comic.koreader_name_hash)
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]
        assert self._pull(self.comic.koreader_name_hash).json()["progress"] == "5"

    def test_hash_case_is_ignored(self) -> None:
        """Upper-case hex matches; the response echoes what was sent."""
        upper = str(self.comic.koreader_hash).upper()
        assert self._push(upper).json()["document"] == upper
        assert self._bookmarks() == [(self.comic.pk, _STORED_PAGE, False)]
        assert self._pull(upper).json()["document"] == upper

    def test_other_users_progress_is_not_pulled(self) -> None:
        """Bookmarks are per user."""
        other = User.objects.create_user(username="other", password="x")  # noqa: S106
        Bookmark.objects.create(user=other, comic=self.comic, page=9)
        assert self._pull(self.comic.koreader_hash).json() == {}


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
        push = self._push(self.private_comic.koreader_hash)
        unknown = self._push(_UNKNOWN_HASH)
        assert push.status_code == unknown.status_code == _HTTP_OK
        assert set(push.json()) == set(unknown.json())
        assert Bookmark.objects.get(comic=self.private_comic).page == _WEB_PAGE
        assert self._pull(self.private_comic.koreader_hash).json() == {}

    def test_age_rating_ceiling(self) -> None:
        """A comic above the user's age-rating ceiling is invisible to sync."""
        rating = AgeRating(name=MetronAgeRatingEnum.ADULT.value)
        rating.presave()
        rating.save()
        adult = self._make_comic(self.library, _OPEN_DIR, "adult", age_rating=rating)
        teen = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        UserAuth.objects.filter(user=self.user).update(age_rating_metron=teen)
        cache.clear()
        assert self._push(adult.koreader_hash).status_code == _HTTP_OK
        assert not Bookmark.objects.filter(comic=adult).exists()
        Bookmark.objects.create(user=self.user, comic=adult, page=9)
        assert self._pull(adult.koreader_hash).json() == {}

    def test_duplicate_hashes(self) -> None:
        """
        Two visible copies of one file share a hash.

        A push updates both; a pull returns the newer bookmark.
        """
        twin = self._make_comic(self.library, _OPEN_DIR, "twin")
        Comic.objects.filter(pk=twin.pk).update(koreader_hash=self.comic.koreader_hash)
        self._push(self.comic.koreader_hash)
        assert self._bookmarks() == [
            (self.comic.pk, _STORED_PAGE, False),
            (twin.pk, _STORED_PAGE, False),
        ]
        Bookmark.objects.filter(comic=twin).update(page=14)
        Bookmark.objects.filter(comic=self.comic).update(
            updated_at=Bookmark.objects.get(comic=twin).updated_at.replace(year=2000)
        )
        assert self._pull(self.comic.koreader_hash).json()["progress"] == "15"


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
            (("x", 0.999, 20), (19, True)),
            (("x", None, 20), None),
            (("3", None, 0), (2, False)),  # Codex hasn't counted pages yet
            ((None, 0.5, 0), None),
            (("3", "0.15", 20), (2, False)),
            (("3", 1.5, 20), (2, False)),  # out-of-range percentage ignored
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


class KOSyncBackfillTestCase(KOSyncTestCase):
    """The janitor job hashes comics imported before the flag existed."""

    def _janitor(self) -> Janitor:
        return Janitor(logger, LIBRARIAN_QUEUE, Lock(), Event())

    def _clear_hashes(self) -> None:
        Comic.objects.update(koreader_hash=None, koreader_name_hash=None)

    def test_backfill_hashes_null_rows(self) -> None:
        """Every comic with a readable file gets both hashes."""
        self._clear_hashes()
        self._janitor().koreader_hash_backfill()
        for comic in Comic.objects.all():
            assert comic.koreader_hash == koreader_partial_md5(comic.path)
            assert comic.koreader_name_hash == koreader_name_md5(comic.path)

    def test_backfill_skips_unreadable_files(self) -> None:
        """A missing file stays null and doesn't stall the run."""
        self._clear_hashes()
        Path(self.comic.path).unlink()
        self._janitor().koreader_hash_backfill()
        assert Comic.objects.get(pk=self.comic.pk).koreader_hash is None
        assert Comic.objects.get(pk=self.private_comic.pk).koreader_hash

    def test_backfill_does_nothing_with_the_flag_off(self) -> None:
        """The nightly run is a no-op while sync is off."""
        _set_flag(on=False)
        cache.clear()
        self._clear_hashes()
        self._janitor().koreader_hash_backfill()
        assert not Comic.objects.filter(koreader_hash__isnull=False).exists()

    def test_turning_the_flag_on_queues_the_backfill(self) -> None:
        """The admin flag hook queues the job."""
        _set_flag(on=False)
        admin = User.objects.create_superuser(
            username="admin",
            email="",
            password="x",  # noqa: S106
        )
        self.client.force_login(admin)
        with patch("codex.views.admin.flag.LIBRARIAN_QUEUE") as queue:
            key = AdminFlagChoices.KOREADER_SYNC.value
            body = {"data": {"type": "flags", "id": key, "attributes": {"on": True}}}
            response = self.client.patch(
                f"/api/v4/admin/flags/{key}",
                data=json.dumps(body),
                content_type="application/json",
            )
        assert response.status_code == _HTTP_OK, response.content
        queued = [call.args[0] for call in queue.put.call_args_list]
        assert any(isinstance(task, JanitorKoreaderHashTask) for task in queued)

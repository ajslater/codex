"""
Logging in keeps a visitor's settings and bookmarks.

``login()`` cycles the session key. The codex session store re-points the
old key's rows to the new key and the ``user_logged_in`` receiver adopts
them into the user, so nothing the visitor set is lost.
"""

import shutil
from datetime import timedelta
from importlib import import_module
from typing import Final, override

from allauth.account.adapter import get_adapter as get_account_adapter
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.cache import caches
from django.db import connection
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

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
from codex.models.settings import SettingsBrowser, SettingsReader
from codex.sessions import SessionStore
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.login_keeps_settings")
_USERNAME: Final = "visitor"
_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_LOGIN_URL: Final = "/api/v4/auth/login"
_REGISTER_URL: Final = "/api/v4/auth/register"
_BROWSER_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
_READER_SETTINGS_URL: Final = "/api/v4/reader/settings"
_HTTP_OK: Final = 200
_HTTP_CREATED: Final = 201
_ORDER_BY: Final = "created_at"
# "W" is the site default, so it would not prove anything survived.
_FIT_TO: Final = "H"
_COMIC_FIT_TO: Final = "O"


def _data(response) -> dict:
    """Unwrap the v4 ``{data, meta, errors}`` envelope."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _make_comic(name: str = "c") -> Comic:
    _TMP_DIR.mkdir(exist_ok=True, parents=True)
    library, _ = Library.objects.get_or_create(path=str(_TMP_DIR))
    publisher, _ = Publisher.objects.get_or_create(name="P")
    imprint, _ = Imprint.objects.get_or_create(name="I", publisher=publisher)
    series, _ = Series.objects.get_or_create(
        name="S", publisher=publisher, imprint=imprint
    )
    volume, _ = Volume.objects.get_or_create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    path = _TMP_DIR / f"{name}.cbz"
    path.touch()
    return Comic.objects.create(
        library=library,
        path=path,
        issue_number=1,
        name=name,
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        size=1,
        file_type="CBZ",
    )


class _LoginTestCase(TestCase):
    """Shared setup: admin flags, empty cache, a client."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        init_admin_flags()
        self.client = Client()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _make_user() -> User:
        return User.objects.create_user(username=_USERNAME, password=_PASSWORD)

    def _login(self) -> None:
        response = self.client.post(
            _LOGIN_URL,
            {"login": _USERNAME, "password": _PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _set_order_by(self) -> None:
        response = self.client.patch(
            _BROWSER_SETTINGS_URL,
            {"orderBy": _ORDER_BY},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _get_order_by(self) -> str:
        response = self.client.get(_BROWSER_SETTINGS_URL)
        assert response.status_code == _HTTP_OK, response.content
        return _data(response)["orderBy"]

    def _session_key(self) -> str:
        return self.client.session.session_key


class BrowserSettingsLoginTests(_LoginTestCase):
    """Anonymous browser settings survive login."""

    def test_password_login_keeps_order_by(self) -> None:
        self._set_order_by()
        self._make_user()

        self._login()

        user = User.objects.get(username=_USERNAME)
        row = SettingsBrowser.objects.get(name="")
        assert row.user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]
        assert row.session_id == self._session_key()  # pyright: ignore[reportAttributeAccessIssue]
        assert row.order_by == _ORDER_BY
        assert self._get_order_by() == _ORDER_BY

    def test_register_then_login_keeps_order_by(self) -> None:
        AdminFlag.objects.filter(key=AdminFlagChoices.REGISTRATION.value).update(
            on=True
        )
        self._set_order_by()

        response = self.client.post(
            _REGISTER_URL,
            {
                "username": _USERNAME,
                "password": _PASSWORD,
                "passwordConfirm": _PASSWORD,
            },
            content_type="application/json",
        )
        assert response.status_code == _HTTP_CREATED, response.content
        self._login()

        assert self._get_order_by() == _ORDER_BY
        assert SettingsBrowser.objects.filter(name="").count() == 1

    def test_users_own_row_wins(self) -> None:
        user = self._make_user()
        user_client = Client()
        user_client.force_login(user)
        response = user_client.patch(
            _BROWSER_SETTINGS_URL,
            {"orderBy": "sort_name"},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        user_row_pk = SettingsBrowser.objects.get(user=user, name="").pk

        self._set_order_by()
        self._login()

        rows = SettingsBrowser.objects.filter(name="")
        assert list(rows.values_list("pk", flat=True)) == [user_row_pk]
        assert self._get_order_by() == "sort_name"

    def test_named_anonymous_row_is_deleted(self) -> None:
        self._set_order_by()
        default_row = SettingsBrowser.objects.get(name="")
        named = SettingsBrowser.objects.create(
            session_id=default_row.session_id,  # pyright: ignore[reportAttributeAccessIssue]
            name="Saved",
            show=default_row.show,
        )
        self._make_user()

        self._login()

        assert not SettingsBrowser.objects.filter(pk=named.pk).exists()
        assert SettingsBrowser.objects.filter(name="").exists()


class ReaderSettingsLoginTests(_LoginTestCase):
    """Anonymous reader settings survive login."""

    def _patch_reader(self, url: str, payload: dict) -> None:
        response = self.client.patch(url, payload, content_type="application/json")
        assert response.status_code == _HTTP_OK, response.content

    def test_global_and_comic_settings_survive(self) -> None:
        comic = _make_comic()
        self._patch_reader(_READER_SETTINGS_URL, {"scope": "global", "fitTo": _FIT_TO})
        comic_url = f"/api/v4/comics/{comic.pk}/reader-settings"
        self._patch_reader(
            comic_url,
            {"scope": "comics", "scopePk": comic.pk, "fitTo": _COMIC_FIT_TO},
        )
        user = self._make_user()

        self._login()

        rows = SettingsReader.objects.all()
        assert rows.count() == 2  # noqa: PLR2004
        assert all(row.user_id == user.pk for row in rows)  # pyright: ignore[reportAttributeAccessIssue]
        assert all(row.session_id is None for row in rows)  # pyright: ignore[reportAttributeAccessIssue]

        response = self.client.get(_READER_SETTINGS_URL, {"scopes": "global"})
        assert response.status_code == _HTTP_OK, response.content
        assert _data(response)["scopes"]["global"]["fitTo"] == _FIT_TO

        response = self.client.get(comic_url, {"scopes": "global,series,comics"})
        assert response.status_code == _HTTP_OK, response.content
        assert _data(response)["scopes"]["comics"]["fitTo"] == _COMIC_FIT_TO

    def test_a_scoped_row_conflicts_only_with_the_same_scope(self) -> None:
        """
        A slot is the client plus every scope column, nulls equal.

        The user's comic row wins over the visitor's row for that comic,
        and does not block the visitor's global row.
        """
        comic = _make_comic()
        user = self._make_user()
        user_row = SettingsReader.objects.create(user=user, comic=comic, fit_to="S")
        self._patch_reader(_READER_SETTINGS_URL, {"scope": "global", "fitTo": _FIT_TO})
        comic_url = f"/api/v4/comics/{comic.pk}/reader-settings"
        self._patch_reader(
            comic_url,
            {"scope": "comics", "scopePk": comic.pk, "fitTo": _COMIC_FIT_TO},
        )

        self._login()

        rows = SettingsReader.objects.filter(user=user)
        assert rows.count() == 2  # noqa: PLR2004
        user_row.refresh_from_db()
        assert user_row.fit_to == "S"
        assert rows.get(comic__isnull=True).fit_to == _FIT_TO

    def test_users_own_global_row_wins(self) -> None:
        user = self._make_user()
        user_row = SettingsReader.objects.create(user=user, fit_to="S")
        self._patch_reader(_READER_SETTINGS_URL, {"scope": "global", "fitTo": _FIT_TO})

        self._login()

        assert list(SettingsReader.objects.values_list("pk", flat=True)) == [
            user_row.pk
        ]


class BookmarkLoginTests(_LoginTestCase):
    """Anonymous bookmarks are adopted at login."""

    def _anonymous_session_key(self) -> str:
        # Any anonymous API call creates the session row.
        self._set_order_by()
        return self._session_key()

    def test_bookmark_is_adopted(self) -> None:
        comic = _make_comic()
        key = self._anonymous_session_key()
        bookmark = Bookmark.objects.create(session_id=key, comic=comic, page=3)
        user = self._make_user()

        self._login()

        bookmark.refresh_from_db()
        assert bookmark.user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]
        assert bookmark.session_id is None  # pyright: ignore[reportAttributeAccessIssue]
        assert bookmark.page == 3  # noqa: PLR2004

    def test_users_bookmark_wins_on_conflict(self) -> None:
        comic = _make_comic()
        other = _make_comic("other")
        key = self._anonymous_session_key()
        user = self._make_user()
        user_bookmark = Bookmark.objects.create(user=user, comic=comic, page=9)
        Bookmark.objects.create(session_id=key, comic=comic, page=1)
        adopted = Bookmark.objects.create(session_id=key, comic=other, page=2)

        self._login()

        assert set(Bookmark.objects.values_list("pk", flat=True)) == {
            user_bookmark.pk,
            adopted.pk,
        }
        user_bookmark.refresh_from_db()
        assert user_bookmark.page == 9  # noqa: PLR2004
        adopted.refresh_from_db()
        assert adopted.user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]

    def test_adopted_bookmarks_keep_their_timestamps(self) -> None:
        """
        Adoption is not reading: "Last Read" order survives the login.

        Stamping every adopted row with the login time collapsed Last Read
        and OPDS Keep Reading into a tie and made weeks-old positions look
        freshly written to OPDS progression and KOReader.
        """
        comics = [_make_comic(f"t{n}") for n in range(2)]
        key = self._anonymous_session_key()
        old = timezone.now() - timedelta(days=30)
        for n, comic in enumerate(comics):
            bookmark = Bookmark.objects.create(session_id=key, comic=comic, page=n)
            Bookmark.objects.filter(pk=bookmark.pk).update(
                updated_at=old + timedelta(hours=n)
            )
        before = dict(Bookmark.objects.values_list("comic_id", "updated_at"))
        user = self._make_user()

        self._login()

        after = dict(
            Bookmark.objects.filter(user=user).values_list("comic_id", "updated_at")
        )
        assert after == before

    def test_adoption_is_set_based(self) -> None:
        """A visitor with many bookmarks costs a constant number of writes."""
        comics = [_make_comic(f"m{n}") for n in range(20)]
        key = self._anonymous_session_key()
        user = self._make_user()
        Bookmark.objects.create(user=user, comic=comics[0], page=7)
        Bookmark.objects.bulk_create(
            Bookmark(session_id=key, comic=comic, page=1) for comic in comics
        )

        with CaptureQueriesContext(connection) as ctx:
            self._login()

        # cycle_key's one re-point of the session id aside, adoption is a
        # delete of the rows the user's own fill and one update of the rest.
        adoption_writes = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].startswith('DELETE FROM "codex_bookmark"')
            or (
                q["sql"].startswith('UPDATE "codex_bookmark"')
                and '"user_id"' in q["sql"].split("WHERE")[0]
            )
        ]
        assert len(adoption_writes) <= 2, adoption_writes  # noqa: PLR2004
        assert Bookmark.objects.filter(user=user).count() == len(comics)
        assert Bookmark.objects.get(user=user, comic=comics[0]).page == 7  # noqa: PLR2004

    def test_users_own_bookmark_is_never_modified(self) -> None:
        comic = _make_comic()
        key = self._anonymous_session_key()
        user = self._make_user()
        mine = Bookmark.objects.create(user=user, comic=comic, page=9)
        stamp = timezone.now() - timedelta(days=3)
        Bookmark.objects.filter(pk=mine.pk).update(updated_at=stamp)
        Bookmark.objects.create(session_id=key, comic=comic, page=1, finished=True)

        self._login()

        mine.refresh_from_db()
        assert (mine.page, mine.finished, mine.updated_at) == (9, False, stamp)


class OIDCLoginTests(_LoginTestCase):
    """allauth's adapter login goes through the same session cycling."""

    def test_adapter_login_keeps_settings(self) -> None:
        comic = _make_comic()
        self._set_order_by()
        key = self._session_key()
        Bookmark.objects.create(session_id=key, comic=comic, page=4)
        SettingsReader.objects.create(session_id=key, fit_to=_FIT_TO)
        user = self._make_user()

        request = RequestFactory().get("/sso/oidc/login/callback/")
        request.session = SessionStore(session_key=key)
        request.user = user
        get_account_adapter(request).login(request, user)

        new_key = request.session.session_key
        assert new_key != key
        assert not Session.objects.filter(session_key=key).exists()
        browser = SettingsBrowser.objects.get(name="")
        assert browser.user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]
        assert browser.session_id == new_key  # pyright: ignore[reportAttributeAccessIssue]
        assert SettingsReader.objects.get().user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]
        assert Bookmark.objects.get().user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]


class SessionStoreTests(TestCase):
    """The store re-points on cycle_key and still cascades on flush."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_engine_is_codex_store(self) -> None:
        engine = import_module(settings.SESSION_ENGINE)
        assert engine.SessionStore is SessionStore
        assert Session.get_session_store_class() is not None

    @staticmethod
    def _new_store() -> SessionStore:
        store = SessionStore()
        store.create()
        return store

    def test_cycle_key_repoints_rows(self) -> None:
        comic = _make_comic()
        store = self._new_store()
        old_key = store.session_key
        reader = SettingsReader.objects.create(session_id=old_key, fit_to=_FIT_TO)
        bookmark = Bookmark.objects.create(session_id=old_key, comic=comic, page=1)

        store.cycle_key()

        new_key = store.session_key
        assert new_key != old_key
        assert not Session.objects.filter(session_key=old_key).exists()
        reader.refresh_from_db()
        bookmark.refresh_from_db()
        assert reader.session_id == new_key  # pyright: ignore[reportAttributeAccessIssue]
        assert bookmark.session_id == new_key  # pyright: ignore[reportAttributeAccessIssue]

    def test_acycle_key_repoints_rows(self) -> None:
        store = self._new_store()
        old_key = store.session_key
        reader = SettingsReader.objects.create(session_id=old_key, fit_to=_FIT_TO)

        async_to_sync(store.acycle_key)()

        assert store.session_key != old_key
        assert not Session.objects.filter(session_key=old_key).exists()
        reader.refresh_from_db()
        assert reader.session_id == store.session_key  # pyright: ignore[reportAttributeAccessIssue]

    def test_flush_deletes_anonymous_and_nulls_user_rows(self) -> None:
        user = User.objects.create_user(username=_USERNAME, password=_PASSWORD)
        store = self._new_store()
        key = store.session_key
        anonymous = SettingsReader.objects.create(session_id=key, fit_to=_FIT_TO)
        owned = SettingsReader.objects.create(
            session_id=key, user=user, fit_to=_FIT_TO, comic=_make_comic()
        )

        store.flush()

        assert not SettingsReader.objects.filter(pk=anonymous.pk).exists()
        owned.refresh_from_db()
        assert owned.session_id is None  # pyright: ignore[reportAttributeAccessIssue]
        assert owned.user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]

    def test_django_login_repoints_and_adopts(self) -> None:
        user = User.objects.create_user(username=_USERNAME, password=_PASSWORD)
        store = self._new_store()
        old_key = store.session_key
        SettingsReader.objects.create(session_id=old_key, fit_to=_FIT_TO)
        request = RequestFactory().post(_LOGIN_URL)
        request.session = store

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        row = SettingsReader.objects.get()
        assert row.user_id == user.pk  # pyright: ignore[reportAttributeAccessIssue]
        assert row.session_id is None  # pyright: ignore[reportAttributeAccessIssue]

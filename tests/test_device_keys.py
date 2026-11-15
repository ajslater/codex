"""
Device keys: named, revocable per-device credentials.

What these tests pin:

* The model: names are unique per user, a user holds at most 32 keys, and
  keys go with their user.
* OPDS takes a key as the Basic password or as a Bearer value, Basic also
  takes the API bearer token as the password, and the account password and
  legacy Bearer token keep working. A key belongs to one username and stops
  working when revoked or when its user is deactivated. ACLs still apply.
* KOReader takes the MD5 of a key or of the API token.
* A key is refused everywhere on ``/api/v4/``, key management included.
* The management API returns the key once, only to its owner.
* ``last_used_at`` is written at most once an hour.
"""

import base64
import hashlib
import json
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Final, override

import pytest
from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.urls.base import set_script_prefix
from django.utils import timezone
from rest_framework.authtoken.models import Token

from codex.choices.admin import AdminFlagChoices
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
from codex.models.api_key import (
    DEVICE_KEY_ALPHABET,
    DEVICE_KEY_LENGTH,
    DEVICE_KEYS_PER_USER_MAX,
    UserApiKey,
)
from codex.models.auth import GroupAuth, UserAuth
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_PASSWORD: Final = "device-key-test-pw"  # noqa: S105
_TMP_DIR: Final = tmp_dir("codex.tests.device_keys")
_OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"
_KEYS_URL: Final = "/api/v4/auth/keys"
_OPDS_V2: Final = "/opds/v2.0/"
_OPDS_V1: Final = "/opds/v1.2/"
_KOSYNC_AUTH: Final = "/koreader/users/auth"
_KOSYNC_ACCEPT: Final = "application/vnd.koreader.v1+json"
_HTTP_OK: Final = 200
_HTTP_CREATED: Final = 201
_HTTP_NO_CONTENT: Final = 204
_HTTP_BAD_REQUEST: Final = 400
_HTTP_UNAUTHORIZED: Final = 401
_HTTP_FORBIDDEN: Final = 403
_HTTP_NOT_FOUND: Final = 404
_REFUSED: Final = frozenset({_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN})
_MID_PAGE: Final = 5


def _basic(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def _md5(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def _set_flag(key: AdminFlagChoices, *, on: bool) -> None:
    AdminFlag.objects.filter(key=key.value).update(on=on)
    cache.clear()


class DeviceKeyModelTestCase(TestCase):
    """The model on its own."""

    @override
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="owner", password=_PASSWORD)  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_key_format(self) -> None:
        """20 characters from the 32-symbol alphabet; only hashes are stored."""
        assert len(set(DEVICE_KEY_ALPHABET)) == 32  # noqa: PLR2004
        api_key, key = UserApiKey.create_for_user(self.user, "Kobo")
        assert len(key) == DEVICE_KEY_LENGTH
        assert set(key) <= set(DEVICE_KEY_ALPHABET)
        assert api_key.prefix == key[:4]
        assert api_key.kosync_digest == _md5(key)
        stored = UserApiKey.objects.filter(pk=api_key.pk).values().get()
        assert key not in {str(value) for value in stored.values()}

    def test_names_are_unique_per_user(self) -> None:
        """Two users may share a key name; one user may not."""
        other = User.objects.create_user(username="other", password=_PASSWORD)
        UserApiKey.create_for_user(self.user, "Kobo")
        UserApiKey.create_for_user(other, "Kobo")
        with transaction.atomic(), pytest.raises(IntegrityError):
            UserApiKey.create_for_user(self.user, "Kobo")

    def test_key_limit(self) -> None:
        """The 33rd key is refused."""
        for index in range(DEVICE_KEYS_PER_USER_MAX):
            UserApiKey.create_for_user(self.user, f"key {index}")
        with pytest.raises(ValidationError):
            UserApiKey.create_for_user(self.user, "one too many")
        assert UserApiKey.objects.filter(user=self.user).count() == (
            DEVICE_KEYS_PER_USER_MAX
        )

    def test_cascade_on_user_delete(self) -> None:
        """Keys go with their user."""
        UserApiKey.create_for_user(self.user, "Kobo")
        self.user.delete()
        assert not UserApiKey.objects.exists()


class DeviceKeyFixture(TestCase):
    """A visible comic, one behind a group, and a user with a key and a token."""

    @override
    def setUp(self) -> None:
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
        self.library = Library.objects.create(path=str(_OPEN_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = self._make_comic(self.library, _OPEN_DIR, "open")  # pyright: ignore[reportUninitializedInstanceVariable]
        private_library = Library.objects.create(path=str(_PRIVATE_DIR))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            private_library, _PRIVATE_DIR, "private"
        )
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="reader", password=_PASSWORD
        )
        self.token = Token.objects.create(user=self.user)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.api_key, self.key = UserApiKey.create_for_user(self.user, "Kobo")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="other", password=_PASSWORD
        )
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
            page_count=11,
            size=42,
            **kwargs,
        )

    def _get(self, url: str, auth: str, **headers):
        return Client().get(url, HTTP_AUTHORIZATION=auth, **headers)


class DeviceKeyOPDSTestCase(DeviceKeyFixture):
    """OPDS Basic and Bearer."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # Anonymous browsing off, so a 200 proves the credential worked.
        _set_flag(AdminFlagChoices.NON_USERS, on=False)

    @staticmethod
    def _position_url(comic) -> str:
        return f"/opds/v2.0/comics/{comic.pk}/position"

    def _assert_reads_own_position(self, auth: str) -> None:
        """Assert the credential resolves this user, not just any user."""
        Bookmark.objects.update_or_create(
            user=self.user, comic=self.comic, defaults={"page": _MID_PAGE}
        )
        response = self._get(self._position_url(self.comic), auth)
        assert response.status_code == _HTTP_OK, response.status_code
        assert response.json()["progression"] == 0.5  # noqa: PLR2004

    def test_unauthenticated_is_refused(self) -> None:
        """The baseline: no credential is a challenge."""
        assert Client().get(_OPDS_V2).status_code == _HTTP_UNAUTHORIZED

    def test_basic_with_a_key(self) -> None:
        auth = _basic(self.user.username, self.key)
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK
        assert self._get(_OPDS_V1, auth).status_code == _HTTP_OK
        self._assert_reads_own_position(auth)

    def test_basic_with_the_legacy_token(self) -> None:
        auth = _basic(self.user.username, self.token.key)
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK
        self._assert_reads_own_position(auth)

    def test_basic_with_the_password_still_works(self) -> None:
        auth = _basic(self.user.username, _PASSWORD)
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK
        self._assert_reads_own_position(auth)

    def test_bearer_with_a_key(self) -> None:
        auth = f"Bearer {self.key}"
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK
        self._assert_reads_own_position(auth)

    def test_legacy_bearer_token_still_works(self) -> None:
        """A Bearer value that is not a key falls through to the token class."""
        auth = f"Bearer {self.token.key}"
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK
        self._assert_reads_own_position(auth)

    def test_bad_bearer_is_refused(self) -> None:
        assert self._get(_OPDS_V2, "Bearer nope").status_code == _HTTP_UNAUTHORIZED

    def test_key_under_the_wrong_username(self) -> None:
        """A key or token only works with its own username."""
        for secret in (self.key, self.token.key):
            auth = _basic(self.other.username, secret)
            assert self._get(_OPDS_V2, auth).status_code == _HTTP_UNAUTHORIZED
            auth = _basic("nobody", secret)
            assert self._get(_OPDS_V2, auth).status_code == _HTTP_UNAUTHORIZED

    def test_revoked_key(self) -> None:
        self.api_key.delete()
        for auth in (_basic(self.user.username, self.key), f"Bearer {self.key}"):
            assert self._get(_OPDS_V2, auth).status_code == _HTTP_UNAUTHORIZED

    def test_inactive_user(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        for auth in (
            _basic(self.user.username, self.key),
            _basic(self.user.username, self.token.key),
            f"Bearer {self.key}",
        ):
            assert self._get(_OPDS_V2, auth).status_code == _HTTP_UNAUTHORIZED

    def test_library_acl_still_applies(self) -> None:
        """A key reaches no further than its user."""
        for auth in (_basic(self.user.username, self.key), f"Bearer {self.key}"):
            response = self._get(self._position_url(self.private_comic), auth)
            assert response.status_code == _HTTP_NOT_FOUND

    def test_age_rating_ceiling_still_applies(self) -> None:
        rating = AgeRating(name=MetronAgeRatingEnum.ADULT.value)
        rating.presave()
        rating.save()
        adult = self._make_comic(self.library, _OPEN_DIR, "adult", age_rating=rating)
        auth = f"Bearer {self.key}"
        assert self._get(self._position_url(adult), auth).status_code == _HTTP_OK
        teen = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        UserAuth.objects.filter(user=self.user).update(age_rating_metron=teen)
        cache.clear()
        response = self._get(self._position_url(adult), auth)
        assert response.status_code == _HTTP_NOT_FOUND

    def test_request_auth_is_the_key(self) -> None:
        """The key that authenticated is ``request.auth``."""
        from rest_framework.test import APIRequestFactory

        from codex.authentication import (
            DeviceKeyBasicAuthentication,
            DeviceKeyBearerAuthentication,
        )

        factory = APIRequestFactory()
        request = factory.get(_OPDS_V2, HTTP_AUTHORIZATION=f"Bearer {self.key}")
        result = DeviceKeyBearerAuthentication().authenticate(request)
        assert result == (self.user, self.api_key)
        request = factory.get(
            _OPDS_V2, HTTP_AUTHORIZATION=_basic(self.user.username, self.key)
        )
        result = DeviceKeyBasicAuthentication().authenticate(request)
        assert result == (self.user, self.api_key)


class DeviceKeyKOSyncTestCase(DeviceKeyFixture):
    """KOReader sends the MD5 of the password typed on the device."""

    @override
    def setUp(self) -> None:
        super().setUp()
        _set_flag(AdminFlagChoices.KOREADER_SYNC, on=True)

    def _auth(self, key_md5: str, username: str | None = None):
        return Client().get(
            _KOSYNC_AUTH,
            HTTP_ACCEPT=_KOSYNC_ACCEPT,
            HTTP_X_AUTH_USER=username or self.user.username,
            HTTP_X_AUTH_KEY=key_md5,
        )

    def test_md5_of_a_key(self) -> None:
        assert self._auth(_md5(self.key)).status_code == _HTTP_OK
        assert self._auth(_md5(self.key).upper()).status_code == _HTTP_OK

    def test_md5_of_the_legacy_token_still_works(self) -> None:
        assert self._auth(_md5(self.token.key)).status_code == _HTTP_OK

    def test_revoked_key(self) -> None:
        self.api_key.delete()
        assert self._auth(_md5(self.key)).status_code == _HTTP_UNAUTHORIZED

    def test_key_under_the_wrong_username(self) -> None:
        response = self._auth(_md5(self.key), username=self.other.username)
        assert response.status_code == _HTTP_UNAUTHORIZED

    def test_raw_key_is_refused(self) -> None:
        """The device sends the MD5, never the key itself."""
        assert self._auth(self.key).status_code == _HTTP_UNAUTHORIZED

    def test_inactive_user(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        assert self._auth(_md5(self.key)).status_code == _HTTP_UNAUTHORIZED


class DeviceKeyScopeTestCase(DeviceKeyFixture):
    """A device key is not an ``/api/v4/`` credential."""

    @override
    def setUp(self) -> None:
        super().setUp()
        _set_flag(AdminFlagChoices.NON_USERS, on=False)
        User.objects.filter(pk=self.user.pk).update(is_staff=True, is_superuser=True)

    def _auths(self) -> tuple[str, ...]:
        return (f"Bearer {self.key}", _basic(self.user.username, self.key))

    def test_browse_is_refused(self) -> None:
        url = "/api/v4/browse/publishers/1"
        assert self._get(url, f"Bearer {self.token.key}").status_code == _HTTP_OK
        for auth in self._auths():
            assert self._get(url, auth).status_code in _REFUSED, auth

    def test_admin_is_refused(self) -> None:
        url = "/api/v4/admin/users"
        assert self._get(url, f"Bearer {self.token.key}").status_code == _HTTP_OK
        for auth in self._auths():
            assert self._get(url, auth).status_code in _REFUSED, auth

    def test_key_management_is_refused(self) -> None:
        for auth in self._auths():
            client = Client()
            assert (
                client.get(_KEYS_URL, HTTP_AUTHORIZATION=auth).status_code in _REFUSED
            )
            response = client.post(
                _KEYS_URL,
                data=json.dumps({"name": "sneaky"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=auth,
            )
            assert response.status_code in _REFUSED
            response = client.delete(
                f"{_KEYS_URL}/{self.api_key.pk}", HTTP_AUTHORIZATION=auth
            )
            assert response.status_code in _REFUSED
        assert UserApiKey.objects.filter(user=self.user).count() == 1


class DeviceKeyAPITestCase(DeviceKeyFixture):
    """Listing, creating, renaming and revoking keys."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def _post(self, client: Client, name: str):
        return client.post(
            _KEYS_URL, data=json.dumps({"name": name}), content_type="application/json"
        )

    def _list(self, client: Client) -> list[dict]:
        response = client.get(_KEYS_URL)
        assert response.status_code == _HTTP_OK
        return response.json()["data"]["keys"]

    def test_key_appears_only_in_the_create_response(self) -> None:
        response = self._post(self.client, "Panels on iPad")
        assert response.status_code == _HTTP_CREATED
        created = response.json()["data"]
        key = created["key"]
        assert created["name"] == "Panels on iPad"
        assert created["prefix"] == key[:4]
        listed = self._list(self.client)
        assert {row["name"] for row in listed} == {"Kobo", "Panels on iPad"}
        assert key not in json.dumps(listed)
        assert self.key not in json.dumps(listed)
        for row in listed:
            assert set(row) == {"pk", "name", "prefix", "createdAt", "lastUsedAt"}
        # And the new key works.
        auth = _basic(self.user.username, key)
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK

    def test_duplicate_name_is_refused(self) -> None:
        response = self._post(self.client, "Kobo")
        assert response.status_code == _HTTP_BAD_REQUEST

    def test_limit_is_a_400(self) -> None:
        for index in range(DEVICE_KEYS_PER_USER_MAX - 1):
            UserApiKey.create_for_user(self.user, f"key {index}")
        response = self._post(self.client, "one too many")
        assert response.status_code == _HTTP_BAD_REQUEST

    def test_rename(self) -> None:
        url = f"{_KEYS_URL}/{self.api_key.pk}"
        response = self.client.patch(
            url, data=json.dumps({"name": "Libra"}), content_type="application/json"
        )
        assert response.status_code == _HTTP_OK
        assert response.json()["data"]["name"] == "Libra"
        self.api_key.refresh_from_db()
        assert self.api_key.name == "Libra"
        # Renaming leaves the key itself alone.
        auth = _basic(self.user.username, self.key)
        _set_flag(AdminFlagChoices.NON_USERS, on=False)
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK

    def test_revoke(self) -> None:
        url = f"{_KEYS_URL}/{self.api_key.pk}"
        assert self.client.delete(url).status_code == _HTTP_NO_CONTENT
        assert not UserApiKey.objects.filter(pk=self.api_key.pk).exists()
        assert self.client.delete(url).status_code == _HTTP_NO_CONTENT

    def test_users_cannot_see_or_touch_each_others_keys(self) -> None:
        other_client = Client()
        other_client.force_login(self.other)
        assert self._list(other_client) == []
        url = f"{_KEYS_URL}/{self.api_key.pk}"
        response = other_client.patch(
            url, data=json.dumps({"name": "mine"}), content_type="application/json"
        )
        assert response.status_code == _HTTP_NOT_FOUND
        assert other_client.delete(url).status_code == _HTTP_NO_CONTENT
        self.api_key.refresh_from_db()
        assert self.api_key.name == "Kobo"

    def test_anonymous_is_refused(self) -> None:
        anon = Client()
        assert anon.get(_KEYS_URL).status_code in _REFUSED
        assert self._post(anon, "anon").status_code in _REFUSED
        assert anon.delete(f"{_KEYS_URL}/{self.api_key.pk}").status_code in _REFUSED
        assert UserApiKey.objects.filter(pk=self.api_key.pk).exists()

    def test_bearer_token_can_manage_keys(self) -> None:
        """The API credential, unlike a key, manages keys."""
        response = Client().get(
            _KEYS_URL, HTTP_AUTHORIZATION=f"Bearer {self.token.key}"
        )
        assert response.status_code == _HTTP_OK


class DeviceKeyLastUsedTestCase(DeviceKeyFixture):
    """``last_used_at`` is coarse on purpose."""

    def _last_used(self):
        return UserApiKey.objects.values_list("last_used_at", flat=True).get(
            pk=self.api_key.pk
        )

    def test_set_and_not_rewritten_within_the_hour(self) -> None:
        assert self._last_used() is None
        auth = f"Bearer {self.key}"
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK
        first = self._last_used()
        assert first is not None
        assert self._get(_OPDS_V2, auth).status_code == _HTTP_OK
        assert self._last_used() == first

    def test_rewritten_after_the_hour(self) -> None:
        stale = timezone.now() - timedelta(hours=2)
        UserApiKey.objects.filter(pk=self.api_key.pk).update(last_used_at=stale)
        assert self._get(_OPDS_V2, f"Bearer {self.key}").status_code == _HTTP_OK
        assert self._last_used() > stale

    def test_kosync_sets_it(self) -> None:
        _set_flag(AdminFlagChoices.KOREADER_SYNC, on=True)
        Client().get(
            _KOSYNC_AUTH,
            HTTP_ACCEPT=_KOSYNC_ACCEPT,
            HTTP_X_AUTH_USER=self.user.username,
            HTTP_X_AUTH_KEY=_md5(self.key),
        )
        assert self._last_used() is not None


class DeviceKeyURLPrefixTestCase(TestCase):
    """``server.url_path_prefix`` carries onto the paths a device is given."""

    def test_reverse_under_a_prefix(self) -> None:
        set_script_prefix("/codex/")
        try:
            assert reverse("opds:v2:start") == "/codex/opds/v2.0/"
            assert reverse("opds:v1:start") == "/codex/opds/v1.2/"
            assert reverse("koreader:users_auth") == "/codex/koreader/users/auth"
            assert reverse("api:v4:auth:keys") == "/codex/api/v4/auth/keys"
        finally:
            set_script_prefix("/")


class DeviceKeyAdminTestCase(DeviceKeyFixture):
    """The admin user list counts keys and can revoke them all."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", email="", password=_PASSWORD
        )
        self.client.force_login(self.admin)
        UserApiKey.create_for_user(self.user, "Boox")

    def _counts(self) -> dict[str, int]:
        response = self.client.get("/api/v4/admin/users")
        assert response.status_code == _HTTP_OK
        return {
            row["attributes"]["username"]: row["attributes"]["deviceKeyCount"]
            for row in response.json()["data"]
        }

    def test_key_count(self) -> None:
        counts = self._counts()
        assert counts["reader"] == 2  # noqa: PLR2004
        assert counts["other"] == 0

    def test_revoke_all(self) -> None:
        url = f"/api/v4/admin/users/{self.user.pk}/revoke-device-keys"
        response = self.client.post(url)
        assert response.status_code == _HTTP_OK
        assert response.json()["data"]["revoked"] == 2  # noqa: PLR2004
        assert not UserApiKey.objects.filter(user=self.user).exists()
        assert self._counts()["reader"] == 0
        # The bearer token is not a device key and survives.
        assert Token.objects.filter(user=self.user).exists()

    def test_revoke_all_is_admin_only(self) -> None:
        client = Client()
        client.force_login(self.user)
        url = f"/api/v4/admin/users/{self.user.pk}/revoke-device-keys"
        assert client.post(url).status_code in _REFUSED
        assert UserApiKey.objects.filter(user=self.user).count() == 2  # noqa: PLR2004

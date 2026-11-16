"""
Logging in with an API key.

What these tests pin:

* OPDS takes a device key or a universal key (an old bearer token, migrated)
  as the Basic password or as a Bearer value, and the account password keeps
  working. A key belongs to one username and stops working when revoked or
  when its user is deactivated. ACLs still apply. A stats key is refused.
* KOReader takes the MD5 of a device key or a universal key.
* Only a universal key logs in to ``/api/v4/``: a device or stats key is
  refused there, key management included.
"""

import json
from typing import Final, override

from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client

from codex.choices.admin import AdminFlagChoices
from codex.choices.api_key import ApiKeyScope
from codex.models import AgeRating, AgeRatingMetron, Bookmark
from codex.models.api_key import UserApiKey
from codex.models.auth import UserAuth
from tests.api_key_fixtures import (
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    KEYS_URL,
    KOSYNC_ACCEPT,
    KOSYNC_AUTH,
    OPDS_V1,
    OPDS_V2,
    OPEN_DIR,
    PASSWORD,
    REFUSED,
    ApiKeyFixture,
    basic,
    md5,
    set_flag,
)

_MID_PAGE: Final = 5


class ApiKeyOPDSTestCase(ApiKeyFixture):
    """OPDS Basic and Bearer."""

    @override
    def setUp(self) -> None:
        super().setUp()
        # Anonymous browsing off, so a 200 proves the credential worked.
        set_flag(AdminFlagChoices.NON_USERS, on=False)

    @staticmethod
    def _position_url(comic) -> str:
        return f"/opds/v2.0/comics/{comic.pk}/position"

    def _assert_reads_own_position(self, auth: str) -> None:
        """Assert the credential resolves this user, not just any user."""
        Bookmark.objects.update_or_create(
            user=self.user, comic=self.comic, defaults={"page": _MID_PAGE}
        )
        response = self._get(self._position_url(self.comic), auth)
        assert response.status_code == HTTP_OK, response.status_code
        assert response.json()["progression"] == 0.5  # noqa: PLR2004

    def test_unauthenticated_is_refused(self) -> None:
        """The baseline: no credential is a challenge."""
        assert Client().get(OPDS_V2).status_code == HTTP_UNAUTHORIZED

    def test_basic_with_a_key(self) -> None:
        auth = basic(self.user.username, self.key)
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK
        assert self._get(OPDS_V1, auth).status_code == HTTP_OK
        self._assert_reads_own_position(auth)

    def test_basic_with_a_universal_key(self) -> None:
        auth = basic(self.user.username, self.token)
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK
        self._assert_reads_own_position(auth)

    def test_basic_with_the_password_still_works(self) -> None:
        auth = basic(self.user.username, PASSWORD)
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK
        self._assert_reads_own_position(auth)

    def test_bearer_with_a_key(self) -> None:
        auth = f"Bearer {self.key}"
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK
        self._assert_reads_own_position(auth)

    def test_bearer_with_a_universal_key(self) -> None:
        """An old bearer token, migrated, still logs in to OPDS."""
        auth = f"Bearer {self.token}"
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK
        self._assert_reads_own_position(auth)

    def test_bad_bearer_is_refused(self) -> None:
        assert self._get(OPDS_V2, "Bearer nope").status_code == HTTP_UNAUTHORIZED

    def test_stats_key_is_refused(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_staff=True)
        _, stats_key = UserApiKey.create_for_user(self.user, "s", ApiKeyScope.STATS)
        for auth in (basic(self.user.username, stats_key), f"Bearer {stats_key}"):
            assert self._get(OPDS_V2, auth).status_code == HTTP_UNAUTHORIZED

    def test_key_under_the_wrong_username(self) -> None:
        """A key only works with its own username."""
        for secret in (self.key, self.token):
            auth = basic(self.other.username, secret)
            assert self._get(OPDS_V2, auth).status_code == HTTP_UNAUTHORIZED
            auth = basic("nobody", secret)
            assert self._get(OPDS_V2, auth).status_code == HTTP_UNAUTHORIZED

    def test_revoked_key(self) -> None:
        self.api_key.delete()
        for auth in (basic(self.user.username, self.key), f"Bearer {self.key}"):
            assert self._get(OPDS_V2, auth).status_code == HTTP_UNAUTHORIZED

    def test_inactive_user(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        for auth in (
            basic(self.user.username, self.key),
            basic(self.user.username, self.token),
            f"Bearer {self.key}",
        ):
            assert self._get(OPDS_V2, auth).status_code == HTTP_UNAUTHORIZED

    def test_library_acl_still_applies(self) -> None:
        """A key reaches no further than its user."""
        for auth in (basic(self.user.username, self.key), f"Bearer {self.key}"):
            response = self._get(self._position_url(self.private_comic), auth)
            assert response.status_code == HTTP_NOT_FOUND

    def test_age_rating_ceiling_still_applies(self) -> None:
        rating = AgeRating(name=MetronAgeRatingEnum.ADULT.value)
        rating.presave()
        rating.save()
        adult = self._make_comic(self.library, OPEN_DIR, "adult", age_rating=rating)
        auth = f"Bearer {self.key}"
        assert self._get(self._position_url(adult), auth).status_code == HTTP_OK
        teen = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        UserAuth.objects.filter(user=self.user).update(age_rating_metron=teen)
        cache.clear()
        response = self._get(self._position_url(adult), auth)
        assert response.status_code == HTTP_NOT_FOUND

    def test_request_auth_is_the_key(self) -> None:
        """The key that authenticated is ``request.auth``."""
        from rest_framework.test import APIRequestFactory

        from codex.authentication import (
            ReaderKeyBasicAuthentication,
            ReaderKeyBearerAuthentication,
        )

        factory = APIRequestFactory()
        request = factory.get(OPDS_V2, HTTP_AUTHORIZATION=f"Bearer {self.key}")
        result = ReaderKeyBearerAuthentication().authenticate(request)
        assert result == (self.user, self.api_key)
        request = factory.get(
            OPDS_V2, HTTP_AUTHORIZATION=basic(self.user.username, self.token)
        )
        result = ReaderKeyBasicAuthentication().authenticate(request)
        assert result == (self.user, self.universal)


class ApiKeyKOSyncTestCase(ApiKeyFixture):
    """KOReader sends the MD5 of the password typed on the device."""

    @override
    def setUp(self) -> None:
        super().setUp()
        set_flag(AdminFlagChoices.KOREADER_SYNC, on=True)

    def _auth(self, key_md5: str, username: str | None = None):
        return Client().get(
            KOSYNC_AUTH,
            HTTP_ACCEPT=KOSYNC_ACCEPT,
            HTTP_X_AUTH_USER=username or self.user.username,
            HTTP_X_AUTH_KEY=key_md5,
        )

    def test_md5_of_a_key(self) -> None:
        assert self._auth(md5(self.key)).status_code == HTTP_OK
        assert self._auth(md5(self.key).upper()).status_code == HTTP_OK

    def test_md5_of_a_universal_key(self) -> None:
        assert self._auth(md5(self.token)).status_code == HTTP_OK

    def test_md5_of_a_stats_key_is_refused(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_staff=True)
        _, stats_key = UserApiKey.create_for_user(self.user, "s", ApiKeyScope.STATS)
        assert self._auth(md5(stats_key)).status_code == HTTP_UNAUTHORIZED

    def test_a_user_with_no_keys_is_refused(self) -> None:
        response = self._auth(md5("anything"), username=self.other.username)
        assert response.status_code == HTTP_UNAUTHORIZED

    def test_revoked_key(self) -> None:
        self.api_key.delete()
        assert self._auth(md5(self.key)).status_code == HTTP_UNAUTHORIZED

    def test_key_under_the_wrong_username(self) -> None:
        response = self._auth(md5(self.key), username=self.other.username)
        assert response.status_code == HTTP_UNAUTHORIZED

    def test_raw_key_is_refused(self) -> None:
        """The device sends the MD5, never the key itself."""
        assert self._auth(self.key).status_code == HTTP_UNAUTHORIZED

    def test_inactive_user(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        assert self._auth(md5(self.key)).status_code == HTTP_UNAUTHORIZED


class ApiKeyScopeTestCase(ApiKeyFixture):
    """Only a universal key is an ``/api/v4/`` credential."""

    @override
    def setUp(self) -> None:
        super().setUp()
        set_flag(AdminFlagChoices.NON_USERS, on=False)
        User.objects.filter(pk=self.user.pk).update(is_staff=True, is_superuser=True)
        self.user.refresh_from_db()
        self.stats, self.stats_key = UserApiKey.create_for_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            self.user, "stats", ApiKeyScope.STATS
        )

    def _auths(self) -> tuple[str, ...]:
        return (
            f"Bearer {self.key}",
            basic(self.user.username, self.key),
            f"Bearer {self.stats_key}",
            basic(self.user.username, self.stats_key),
        )

    def test_browse_is_refused(self) -> None:
        url = "/api/v4/browse/publishers/1"
        assert self._get(url, f"Bearer {self.token}").status_code == HTTP_OK
        for auth in self._auths():
            assert self._get(url, auth).status_code in REFUSED, auth

    def test_admin_is_refused(self) -> None:
        url = "/api/v4/admin/users"
        assert self._get(url, f"Bearer {self.token}").status_code == HTTP_OK
        for auth in self._auths():
            assert self._get(url, auth).status_code in REFUSED, auth

    def test_key_management_is_refused(self) -> None:
        for auth in self._auths():
            client = Client()
            assert client.get(KEYS_URL, HTTP_AUTHORIZATION=auth).status_code in REFUSED
            response = client.post(
                KEYS_URL,
                data=json.dumps({"name": "sneaky"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=auth,
            )
            assert response.status_code in REFUSED
            response = client.delete(
                f"{KEYS_URL}/{self.api_key.pk}", HTTP_AUTHORIZATION=auth
            )
            assert response.status_code in REFUSED
        assert UserApiKey.objects.filter(user=self.user).count() == 3  # noqa: PLR2004

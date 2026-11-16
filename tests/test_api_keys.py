"""
API keys: named, revocable, hashed credentials with a scope.

What these tests pin:

* The model: names are unique per user, a user holds at most 32 keys of
  each scope, keys go with their user, and nobody can make a universal key.
* The removed token and server API key endpoints are gone.
* ``last_used_at`` is written at most once an hour.

Logging in with a key is in ``test_api_keys_auth.py``; the management API
and the admin user list are in ``test_api_keys_api.py``.
"""

import json
from datetime import timedelta
from typing import override

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import resolve, reverse
from django.urls.base import set_script_prefix
from django.utils import timezone

from codex.choices.admin import AdminFlagChoices
from codex.choices.api_key import ApiKeyScope
from codex.models.api_key import (
    API_KEY_ALPHABET,
    API_KEY_LENGTH,
    API_KEYS_PER_SCOPE_MAX,
    UserApiKey,
)
from tests.api_key_fixtures import (
    HTTP_FOUND,
    HTTP_OK,
    KOSYNC_ACCEPT,
    KOSYNC_AUTH,
    OPDS_V2,
    ApiKeyFixture,
    md5,
    set_flag,
)
from tests.reader_fixtures import PASSWORD


class ApiKeyModelTestCase(TestCase):
    """The model on its own."""

    @override
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="owner", password=PASSWORD)  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_key_format(self) -> None:
        """20 characters from the 32-symbol alphabet; only hashes are stored."""
        assert len(set(API_KEY_ALPHABET)) == 32  # noqa: PLR2004
        api_key, key = UserApiKey.create_for_user(self.user, "Kobo")
        assert api_key.scope == ApiKeyScope.DEVICE
        assert len(key) == API_KEY_LENGTH
        assert set(key) <= set(API_KEY_ALPHABET)
        assert api_key.prefix == key[:4]
        assert api_key.kosync_digest == md5(key)
        stored = UserApiKey.objects.filter(pk=api_key.pk).values().get()
        assert key not in {str(value) for value in stored.values()}

    def test_names_are_unique_per_user(self) -> None:
        """Two users may share a key name; one user may not."""
        other = User.objects.create_user(username="other", password=PASSWORD)
        UserApiKey.create_for_user(self.user, "Kobo")
        UserApiKey.create_for_user(other, "Kobo")
        with transaction.atomic(), pytest.raises(IntegrityError):
            UserApiKey.create_for_user(self.user, "Kobo")

    def test_key_limit(self) -> None:
        """The 33rd key of a scope is refused; another scope has its own 32."""
        for index in range(API_KEYS_PER_SCOPE_MAX):
            UserApiKey.create_for_user(self.user, f"key {index}")
        with pytest.raises(ValidationError):
            UserApiKey.create_for_user(self.user, "one too many")
        assert UserApiKey.objects.filter(user=self.user).count() == (
            API_KEYS_PER_SCOPE_MAX
        )
        UserApiKey.create_for_user(self.user, "stats", ApiKeyScope.STATS)

    def test_universal_keys_cannot_be_made(self) -> None:
        """Universal keys come only from migrated bearer tokens."""
        with pytest.raises(ValidationError):
            UserApiKey.create_for_user(self.user, "all", ApiKeyScope.UNIVERSAL)
        assert not UserApiKey.objects.exists()

    def test_cascade_on_user_delete(self) -> None:
        """Keys go with their user."""
        UserApiKey.create_for_user(self.user, "Kobo")
        self.user.delete()
        assert not UserApiKey.objects.exists()


class ApiKeyLastUsedTestCase(ApiKeyFixture):
    """``last_used_at`` is coarse on purpose."""

    def _last_used(self):
        return UserApiKey.objects.values_list("last_used_at", flat=True).get(
            pk=self.api_key.pk
        )

    def test_set_and_not_rewritten_within_the_hour(self) -> None:
        assert self._last_used() is None
        auth = f"Bearer {self.key}"
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK
        first = self._last_used()
        assert first is not None
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK
        assert self._last_used() == first

    def test_rewritten_after_the_hour(self) -> None:
        stale = timezone.now() - timedelta(hours=2)
        UserApiKey.objects.filter(pk=self.api_key.pk).update(last_used_at=stale)
        assert self._get(OPDS_V2, f"Bearer {self.key}").status_code == HTTP_OK
        assert self._last_used() > stale

    def test_kosync_sets_it(self) -> None:
        set_flag(AdminFlagChoices.KOREADER_SYNC, on=True)
        Client().get(
            KOSYNC_AUTH,
            HTTP_ACCEPT=KOSYNC_ACCEPT,
            HTTP_X_AUTH_USER=self.user.username,
            HTTP_X_AUTH_KEY=md5(self.key),
        )
        assert self._last_used() is not None


class ApiKeyURLPrefixTestCase(TestCase):
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


class RemovedRoutesTestCase(TestCase):
    """Nothing mints a token or shows a server-wide key any more."""

    @override
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", email="", password=PASSWORD
        )
        self.client.force_login(self.admin)

    def test_gone(self) -> None:
        """Each falls to the catch-all, which serves nothing but a redirect."""
        for method, url in (
            ("get", "/api/v4/auth/token"),
            ("put", "/api/v4/auth/token"),
            ("get", "/api/v4/admin/api-key"),
            ("post", "/api/v4/admin/api-key"),
            ("post", f"/api/v4/admin/users/{self.admin.pk}/revoke-device-keys"),
        ):
            assert resolve(url).url_name == "catchall", url
            response = getattr(self.client, method)(url)
            assert response.status_code == HTTP_FOUND, (method, url)
        assert not UserApiKey.objects.exists()

    def test_login_returns_no_token(self) -> None:
        client = Client()
        response = client.post(
            "/api/v4/auth/login",
            data=json.dumps({"login": "admin", "password": PASSWORD}),
            content_type="application/json",
        )
        assert response.status_code == HTTP_OK, response.content
        assert "token" not in json.dumps(response.json())

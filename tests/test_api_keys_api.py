"""
Managing API keys.

What these tests pin:

* The management API returns the key once, only to its owner; only staff
  make stats keys; the reserved name and the universal key stay put.
* The admin user list counts keys of every scope and revokes them all.
* Every revoke leaves a tombstone holding only the key's digest, so a
  backup restore cannot bring the key back. Deleting a user does not: the
  restore brings the whole account back, keys included.
"""

import json
from typing import override

from django.contrib.auth.models import User
from django.test import Client

from codex.choices.admin import AdminFlagChoices
from codex.choices.api_key import UNIVERSAL_KEY_NAME, ApiKeyScope
from codex.models.api_key import API_KEYS_PER_SCOPE_MAX, RevokedApiKey, UserApiKey
from tests.api_key_fixtures import (
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_OK,
    KEYS_URL,
    OPDS_V2,
    REFUSED,
    ApiKeyFixture,
    basic,
    set_flag,
)
from tests.reader_fixtures import PASSWORD


class ApiKeyAPITestCase(ApiKeyFixture):
    """Listing, creating, renaming and revoking keys."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def _post(self, client: Client, name: str, scope: str | None = None):
        data: dict[str, str] = {"name": name}
        if scope:
            data["scope"] = scope
        return client.post(
            KEYS_URL, data=json.dumps(data), content_type="application/json"
        )

    def _list(self, client: Client) -> list[dict]:
        response = client.get(KEYS_URL)
        assert response.status_code == HTTP_OK
        return response.json()["data"]["keys"]

    def _assert_listing_hides_keys(self, key: str) -> None:
        """Assert the listing shows every key's metadata and no key's secret."""
        listed = self._list(self.client)
        assert {row["name"]: row["scope"] for row in listed} == {
            "Kobo": ApiKeyScope.DEVICE,
            "Panels on iPad": ApiKeyScope.DEVICE,
            UNIVERSAL_KEY_NAME: ApiKeyScope.UNIVERSAL,
        }
        for secret in (key, self.key, self.token):
            assert secret not in json.dumps(listed)
        for row in listed:
            assert set(row) == {
                "pk",
                "name",
                "scope",
                "prefix",
                "createdAt",
                "lastUsedAt",
            }

    def test_key_appears_only_in_the_create_response(self) -> None:
        response = self._post(self.client, "Panels on iPad")
        assert response.status_code == HTTP_CREATED
        created = response.json()["data"]
        key = created["key"]
        assert created["name"] == "Panels on iPad"
        assert created["scope"] == ApiKeyScope.DEVICE
        assert created["prefix"] == key[:4]
        self._assert_listing_hides_keys(key)
        # And the new key works.
        auth = basic(self.user.username, key)
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK

    def test_duplicate_name_is_refused(self) -> None:
        response = self._post(self.client, "Kobo")
        assert response.status_code == HTTP_BAD_REQUEST

    def test_stats_keys_are_for_staff(self) -> None:
        response = self._post(self.client, "stats", ApiKeyScope.STATS)
        assert response.status_code == HTTP_FORBIDDEN
        User.objects.filter(pk=self.user.pk).update(is_staff=True)
        response = self._post(self.client, "stats", ApiKeyScope.STATS)
        assert response.status_code == HTTP_CREATED
        assert response.json()["data"]["scope"] == ApiKeyScope.STATS

    def test_universal_keys_cannot_be_made(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_staff=True, is_superuser=True)
        response = self._post(self.client, "everything", ApiKeyScope.UNIVERSAL)
        assert response.status_code == HTTP_BAD_REQUEST
        assert UserApiKey.objects.filter(scope=ApiKeyScope.UNIVERSAL).count() == 1

    def test_the_reserved_name_is_refused(self) -> None:
        self.universal.delete()
        assert self._post(self.client, UNIVERSAL_KEY_NAME).status_code == (
            HTTP_BAD_REQUEST
        )
        url = f"{KEYS_URL}/{self.api_key.pk}"
        response = self.client.patch(
            url,
            data=json.dumps({"name": UNIVERSAL_KEY_NAME}),
            content_type="application/json",
        )
        assert response.status_code == HTTP_BAD_REQUEST

    def test_a_universal_key_cannot_be_renamed_but_can_be_revoked(self) -> None:
        url = f"{KEYS_URL}/{self.universal.pk}"
        response = self.client.patch(
            url, data=json.dumps({"name": "mine"}), content_type="application/json"
        )
        assert response.status_code == HTTP_BAD_REQUEST
        assert self.client.delete(url).status_code == HTTP_NO_CONTENT
        assert not UserApiKey.objects.filter(pk=self.universal.pk).exists()

    def test_limit_is_a_400(self) -> None:
        for index in range(API_KEYS_PER_SCOPE_MAX - 1):
            UserApiKey.create_for_user(self.user, f"key {index}")
        response = self._post(self.client, "one too many")
        assert response.status_code == HTTP_BAD_REQUEST

    def test_rename(self) -> None:
        url = f"{KEYS_URL}/{self.api_key.pk}"
        response = self.client.patch(
            url, data=json.dumps({"name": "Libra"}), content_type="application/json"
        )
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["name"] == "Libra"
        self.api_key.refresh_from_db()
        assert self.api_key.name == "Libra"
        # Renaming leaves the key itself alone.
        auth = basic(self.user.username, self.key)
        set_flag(AdminFlagChoices.NON_USERS, on=False)
        assert self._get(OPDS_V2, auth).status_code == HTTP_OK

    def test_revoke(self) -> None:
        url = f"{KEYS_URL}/{self.api_key.pk}"
        assert self.client.delete(url).status_code == HTTP_NO_CONTENT
        assert not UserApiKey.objects.filter(pk=self.api_key.pk).exists()
        assert self.client.delete(url).status_code == HTTP_NO_CONTENT

    def test_revoke_leaves_a_tombstone_of_the_digest_only(self) -> None:
        url = f"{KEYS_URL}/{self.api_key.pk}"
        assert self.client.delete(url).status_code == HTTP_NO_CONTENT
        tombstones = list(RevokedApiKey.objects.values())
        assert len(tombstones) == 1
        tombstone = tombstones[0]
        assert set(tombstone) == {"id", "digest", "revoked_at"}
        assert tombstone["digest"] == self.api_key.digest
        assert tombstone["revoked_at"] is not None
        # A second, idempotent revoke adds nothing.
        assert self.client.delete(url).status_code == HTTP_NO_CONTENT
        assert RevokedApiKey.objects.count() == 1

    def test_revoking_another_users_key_leaves_no_tombstone(self) -> None:
        other_client = Client()
        other_client.force_login(self.other)
        url = f"{KEYS_URL}/{self.api_key.pk}"
        assert other_client.delete(url).status_code == HTTP_NO_CONTENT
        assert not RevokedApiKey.objects.exists()

    def test_users_cannot_see_or_touch_each_others_keys(self) -> None:
        other_client = Client()
        other_client.force_login(self.other)
        assert self._list(other_client) == []
        url = f"{KEYS_URL}/{self.api_key.pk}"
        response = other_client.patch(
            url, data=json.dumps({"name": "mine"}), content_type="application/json"
        )
        assert response.status_code == HTTP_NOT_FOUND
        assert other_client.delete(url).status_code == HTTP_NO_CONTENT
        self.api_key.refresh_from_db()
        assert self.api_key.name == "Kobo"

    def test_anonymous_is_refused(self) -> None:
        anon = Client()
        assert anon.get(KEYS_URL).status_code in REFUSED
        assert self._post(anon, "anon").status_code in REFUSED
        assert anon.delete(f"{KEYS_URL}/{self.api_key.pk}").status_code in REFUSED
        assert UserApiKey.objects.filter(pk=self.api_key.pk).exists()

    def test_a_universal_key_can_manage_keys(self) -> None:
        """The full API credential, unlike a device key, manages keys."""
        response = Client().get(KEYS_URL, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        assert response.status_code == HTTP_OK


class ApiKeyAdminTestCase(ApiKeyFixture):
    """The admin user list counts keys and can revoke them all."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", email="", password=PASSWORD
        )
        self.client.force_login(self.admin)
        UserApiKey.create_for_user(self.user, "Boox")

    def _counts(self) -> dict[str, int]:
        response = self.client.get("/api/v4/admin/users")
        assert response.status_code == HTTP_OK
        return {
            row["attributes"]["username"]: row["attributes"]["apiKeyCount"]
            for row in response.json()["data"]
        }

    def test_key_count(self) -> None:
        """Every scope counts."""
        counts = self._counts()
        assert counts["reader"] == 3  # noqa: PLR2004
        assert counts["other"] == 0

    def test_revoke_all(self) -> None:
        """Every scope goes, the universal key included."""
        url = f"/api/v4/admin/users/{self.user.pk}/revoke-keys"
        response = self.client.post(url)
        assert response.status_code == HTTP_OK
        assert response.json()["data"]["revoked"] == 3  # noqa: PLR2004
        assert not UserApiKey.objects.filter(user=self.user).exists()
        assert self._counts()["reader"] == 0

    def test_revoke_all_leaves_a_tombstone_for_each_key(self) -> None:
        digests = set(
            UserApiKey.objects.filter(user=self.user).values_list("digest", flat=True)
        )
        url = f"/api/v4/admin/users/{self.user.pk}/revoke-keys"
        assert self.client.post(url).status_code == HTTP_OK
        tombstoned = set(RevokedApiKey.objects.values_list("digest", flat=True))
        assert tombstoned == digests

    def test_deleting_a_user_leaves_no_tombstone(self) -> None:
        """A restore brings a deleted user back whole, keys included."""
        self.user.delete()
        assert not UserApiKey.objects.filter(user_id=self.user.pk).exists()
        assert not RevokedApiKey.objects.exists()

    def test_revoke_all_is_admin_only(self) -> None:
        client = Client()
        client.force_login(self.user)
        url = f"/api/v4/admin/users/{self.user.pk}/revoke-keys"
        assert client.post(url).status_code in REFUSED
        assert UserApiKey.objects.filter(user=self.user).count() == 3  # noqa: PLR2004

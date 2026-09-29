"""Tests for deleting saved browser views."""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models.settings import (
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserLastRoute,
)
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_CREATED: Final = 201
_HTTP_NO_CONTENT: Final = 204
_HTTP_NOT_FOUND: Final = 404
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
_SAVED_URL: Final = "/api/v4/browse/publishers/saved-settings"


def _login(username: str) -> tuple[User, Client]:
    user = User.objects.create_user(username=username, password=_TEST_PASSWORD)
    client = Client()
    client.force_login(user)
    return user, client


def _save_view(client: Client, name: str) -> SettingsBrowser:
    """Create the current settings row, then save it under ``name``."""
    client.patch(
        _SETTINGS_URL,
        data=json.dumps({"orderBy": "created_at"}),
        content_type="application/json",
    )
    response = client.post(
        _SAVED_URL,
        data=json.dumps({"name": name}),
        content_type="application/json",
    )
    assert response.status_code == _HTTP_CREATED, response.content
    return SettingsBrowser.objects.get(name=name)


class SavedSettingsDeleteTestCase(TestCase):
    """DELETE on a saved view removes only the caller's own named row."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        self.user, self.client = _login("saved_delete_owner")  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_delete_removes_the_view_and_its_rows(self):
        saved = _save_view(self.client, "Added Recently")

        response = self.client.delete(f"{_SAVED_URL}/{saved.pk}")

        assert response.status_code == _HTTP_NO_CONTENT, response.content
        assert not SettingsBrowser.objects.filter(pk=saved.pk).exists()
        assert not SettingsBrowserFilters.objects.filter(browser_id=saved.pk).exists()
        assert not SettingsBrowserLastRoute.objects.filter(browser_id=saved.pk).exists()
        # The live settings the view was saved from are untouched.
        assert SettingsBrowser.objects.filter(user=self.user, name="").exists()

    def test_deleted_view_leaves_the_list(self):
        keep = _save_view(self.client, "Keep")
        drop = _save_view(self.client, "Drop")

        self.client.delete(f"{_SAVED_URL}/{drop.pk}")

        listed = self.client.get(_SAVED_URL).json()["data"]["savedSettings"]
        assert listed == [{"pk": keep.pk, "name": "Keep"}]

    def test_another_users_view_is_not_found(self):
        _other, other_client = _login("saved_delete_other")
        theirs = _save_view(other_client, "Theirs")

        response = self.client.delete(f"{_SAVED_URL}/{theirs.pk}")

        assert response.status_code == _HTTP_NOT_FOUND, response.content
        assert SettingsBrowser.objects.filter(pk=theirs.pk).exists()

    def test_current_settings_row_is_not_found(self):
        _save_view(self.client, "Anything")
        current = SettingsBrowser.objects.get(user=self.user, name="")

        response = self.client.delete(f"{_SAVED_URL}/{current.pk}")

        assert response.status_code == _HTTP_NOT_FOUND, response.content
        assert SettingsBrowser.objects.filter(pk=current.pk).exists()

    def test_unknown_pk_is_not_found(self):
        response = self.client.delete(f"{_SAVED_URL}/999999")
        assert response.status_code == _HTTP_NOT_FOUND, response.content

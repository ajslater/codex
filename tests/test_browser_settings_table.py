"""Tests for the new browser table-view settings fields."""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.browser import (
    BROWSER_TABLE_COVER_SIZE_CHOICES,
    BROWSER_VIEW_MODE_CHOICES,
)
from codex.models.settings import SettingsBrowser
from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
_SETTINGS_URL: Final = "/api/v3/r/settings"


class BrowserTableSettingsModelTestCase(TestCase):
    """Verify the new table-view fields are wired with correct defaults."""

    def test_direct_keys_includes_table_view_fields(self):
        for key in ("view_mode", "table_columns", "table_cover_size"):
            assert key in SettingsBrowser.DIRECT_KEYS

    def test_view_mode_default_is_cover(self):
        field = SettingsBrowser._meta.get_field("view_mode")
        assert field.default == "cover"
        assert "cover" in BROWSER_VIEW_MODE_CHOICES
        assert "table" in BROWSER_VIEW_MODE_CHOICES

    def test_table_columns_default_is_empty_dict(self):
        field = SettingsBrowser._meta.get_field("table_columns")
        # JSONField stores a callable default; it returns an empty dict.
        assert field.default() == {}

    def test_table_cover_size_default_is_sm(self):
        field = SettingsBrowser._meta.get_field("table_cover_size")
        assert field.default == "sm"
        assert "sm" in BROWSER_TABLE_COVER_SIZE_CHOICES


class BrowserTableSettingsSerializerTestCase(TestCase):
    """Validate the serializer accepts and rejects table-view payloads."""

    def test_view_mode_table_validates(self):
        s = BrowserSettingsSerializer(data={"view_mode": "table"})
        assert s.is_valid(), s.errors
        assert s.validated_data["view_mode"] == "table"

    def test_view_mode_invalid_rejected(self):
        s = BrowserSettingsSerializer(data={"view_mode": "spreadsheet"})
        assert not s.is_valid()
        assert "view_mode" in s.errors

    def test_table_columns_dict_of_lists_validates(self):
        payload = {"table_columns": {"c": ["cover", "name"]}}
        s = BrowserSettingsSerializer(data=payload)
        assert s.is_valid(), s.errors
        assert s.validated_data["table_columns"] == {"c": ["cover", "name"]}

    def test_table_columns_invalid_top_group_rejected(self):
        s = BrowserSettingsSerializer(
            data={"table_columns": {"x": ["cover"]}},
        )
        assert not s.is_valid()
        assert "table_columns" in s.errors

    def test_table_columns_deprecated_keys_coerced(self):
        """
        Stored settings using ``issue_number`` migrate to ``issue``.

        Stored settings predating the column registry's collapse of
        ``issue_number`` and ``issue_suffix`` round-trip through the
        validator without raising — ``issue_number`` becomes ``issue``,
        and ``issue_suffix`` is dropped (the suffix is now part of the
        compound ``issue`` cell).
        """
        s = BrowserSettingsSerializer(
            data={
                "table_columns": {
                    "c": ["cover", "name", "issue_number", "issue_suffix"]
                }
            }
        )
        assert s.is_valid(), s.errors
        assert s.validated_data["table_columns"] == {"c": ["cover", "name", "issue"]}

    def test_table_columns_invalid_column_key_rejected(self):
        s = BrowserSettingsSerializer(
            data={"table_columns": {"c": ["cover", "phantom_column"]}},
        )
        assert not s.is_valid()
        assert "table_columns" in s.errors

    def test_table_cover_size_sm_validates(self):
        s = BrowserSettingsSerializer(data={"table_cover_size": "sm"})
        assert s.is_valid(), s.errors

    def test_table_cover_size_invalid_rejected(self):
        s = BrowserSettingsSerializer(data={"table_cover_size": "huge"})
        assert not s.is_valid()


class BrowserTableSettingsRoundTripTestCase(TestCase):
    """End-to-end PATCH/GET/DELETE through the settings HTTP endpoint."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        user = User.objects.create_user(
            username="table_settings_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    def _patch(self, payload: dict):
        return self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _get(self) -> dict:
        response = self.client.get(_SETTINGS_URL)
        assert response.status_code == _HTTP_OK, response.content
        return response.json()

    def test_default_get_includes_new_fields(self):
        body = self._get()
        # Response is camelCased.
        assert body.get("viewMode") == "cover"
        assert body.get("tableColumns") == {}
        assert body.get("tableCoverSize") == "sm"

    def test_patch_view_mode_persists(self):
        response = self._patch({"viewMode": "table"})
        assert response.status_code == _HTTP_OK, response.content
        body = self._get()
        assert body["viewMode"] == "table"

    def test_patch_table_columns_persists(self):
        cols = {"c": ["cover", "name", "issue"]}
        response = self._patch({"tableColumns": cols})
        assert response.status_code == _HTTP_OK, response.content
        body = self._get()
        assert body["tableColumns"] == cols

    def test_patch_table_columns_invalid_top_group_rejected(self):
        response = self._patch({"tableColumns": {"x": ["cover"]}})
        assert response.status_code == _HTTP_BAD_REQUEST

    def test_patch_table_cover_size_persists(self):
        response = self._patch({"tableCoverSize": "sm"})
        assert response.status_code == _HTTP_OK, response.content
        body = self._get()
        assert body["tableCoverSize"] == "sm"

    def test_delete_resets_table_view_fields(self):
        # First customize
        self._patch(
            {
                "viewMode": "table",
                "tableColumns": {"c": ["cover", "name"]},
            }
        )
        # Then reset
        response = self.client.delete(_SETTINGS_URL)
        assert response.status_code == _HTTP_OK, response.content
        body = self._get()
        assert body["viewMode"] == "cover"
        assert body["tableColumns"] == {}
        assert body["tableCoverSize"] == "sm"

    def test_get_with_table_columns_query_string(self):
        """
        GET path: ``?tableColumns={"c":[...]}`` round-trips.

        Frontend always sends settings as URL-encoded JSON in query
        params. Without the JSONFieldSerializer parse step the
        DictField sees a literal string and 400s.
        """
        cols = {"c": ["cover", "name", "issue"]}
        url = f"{_SETTINGS_URL}?tableColumns={json.dumps(cols)}"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

    def test_patch_filters_dict_round_trips(self):
        """Regression: PATCH with non-empty filters must persist (was 400)."""
        response = self._patch({"filters": {"genres": [12, 34]}})
        assert response.status_code == _HTTP_OK, response.content
        body = self._get()
        assert body["filters"]["genres"] == [12, 34]

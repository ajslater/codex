"""Tests for the new browser table-view settings fields."""

from django.test import TestCase

from codex.choices.browser import (
    BROWSER_TABLE_COVER_SIZE_CHOICES,
    BROWSER_VIEW_MODE_CHOICES,
)
from codex.models.settings import SettingsBrowser


class BrowserTableSettingsDefaultsTestCase(TestCase):
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
        assert "xs" in BROWSER_TABLE_COVER_SIZE_CHOICES
        assert "sm" in BROWSER_TABLE_COVER_SIZE_CHOICES

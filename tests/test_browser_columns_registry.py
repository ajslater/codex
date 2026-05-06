"""Consistency tests for the browser table-view column registry."""

from django.test import TestCase

from codex.choices.browser import (
    BROWSER_TABLE_COLUMNS,
    BROWSER_TABLE_DEFAULT_COLUMNS,
    BROWSER_TOP_GROUP_CHOICES,
)
from codex.views.browser.columns import (
    default_columns_for,
    is_m2m,
    is_sortable,
    sort_key_for,
)

_REQUIRED_ENTRY_KEYS = frozenset(
    {"label", "sort_key", "m2m", "editable", "edit_widget"}
)


class BrowserTableColumnsRegistryTestCase(TestCase):
    """Pin the registry's invariants."""

    def test_every_entry_has_required_keys(self):
        for key, entry in BROWSER_TABLE_COLUMNS.items():
            missing = _REQUIRED_ENTRY_KEYS - set(entry.keys())
            assert not missing, f"{key} missing keys {missing}"

    def test_every_entry_has_string_label(self):
        for key, entry in BROWSER_TABLE_COLUMNS.items():
            label = entry["label"]
            assert isinstance(label, str), f"{key} label not a string"
            assert label, f"{key} label is empty"

    def test_sort_key_is_string_or_none(self):
        for key, entry in BROWSER_TABLE_COLUMNS.items():
            assert entry["sort_key"] is None or isinstance(entry["sort_key"], str), (
                f"{key} sort_key invalid"
            )

    def test_m2m_columns_are_not_sortable_in_v1(self):
        for key, entry in BROWSER_TABLE_COLUMNS.items():
            if entry["m2m"]:
                assert entry["sort_key"] is None, (
                    f"{key} is m2m but has sort_key set; m2m sorting is Phase 7"
                )

    def test_editable_is_false_in_v1(self):
        for key, entry in BROWSER_TABLE_COLUMNS.items():
            assert entry["editable"] is False, f"{key} editable=True before its time"


class BrowserTableDefaultColumnsTestCase(TestCase):
    """Pin the per-top-group default columns map."""

    def test_keys_are_valid_top_groups(self):
        for key in BROWSER_TABLE_DEFAULT_COLUMNS:
            assert key in BROWSER_TOP_GROUP_CHOICES, f"{key} not a top-group"

    def test_columns_reference_registry(self):
        valid = set(BROWSER_TABLE_COLUMNS.keys())
        for top_group, columns in BROWSER_TABLE_DEFAULT_COLUMNS.items():
            unknown = set(columns) - valid
            assert not unknown, f"{top_group} references unknown columns {unknown}"

    def test_comic_defaults_match_plan(self):
        # Locked in Phase 0; if this changes the plan doc must change too.
        assert default_columns_for("c") == (
            "cover",
            "name",
            "issue_number",
            "series_name",
            "volume_name",
            "year",
            "page_count",
            "size",
        )

    def test_publisher_defaults_minimal(self):
        assert default_columns_for("p") == ("cover", "name", "child_count")

    def test_unknown_top_group_returns_empty(self):
        assert default_columns_for("zz") == ()


class BrowserTableHelperTestCase(TestCase):
    """Pin the helper functions."""

    def test_is_sortable_known_keys(self):
        assert is_sortable("name")
        assert is_sortable("issue_number")
        assert not is_sortable("cover")
        assert not is_sortable("genres")

    def test_is_m2m_known_keys(self):
        assert is_m2m("genres")
        assert is_m2m("tags")
        assert not is_m2m("name")
        assert not is_m2m("cover")

    def test_sort_key_for_known_keys(self):
        assert sort_key_for("name") == "sort_name"
        assert sort_key_for("issue_number") == "issue_number"
        assert sort_key_for("cover") is None

    def test_unknown_column_returns_falsy(self):
        assert not is_sortable("phantom_column")
        assert not is_m2m("phantom_column")
        assert sort_key_for("phantom_column") is None

"""
Phase 2 value-flip: the collection vocabulary round-trips end to end.

After the ``Group`` enum + DB migration flip, browser settings speak the
collection vocabulary on the wire AND in storage (``"publishers"``, no char
dialect, no dummy ``0`` root). These pin the API PATCH→GET round-trip and the
underlying row values — proving the value-flip + the 0043 migration.
"""

import importlib
import json
import shutil
from pathlib import Path
from typing import Final, override

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models.admin import AdminFlag
from codex.models.settings import SettingsBrowser
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.flip")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"

# Migration filenames start with digits, so importlib is the only way to reach
# the helpers (mirrors tests/test_critical_rating.py).
_MIGRATION = importlib.import_module("codex.migrations.0043_comicbox_tagging_defaults")
_remap_table_columns_keys = _MIGRATION._remap_table_columns_keys  # noqa: SLF001
_sb_migrate_browser_rows = _MIGRATION._sb_migrate_browser_rows  # noqa: SLF001
_CHAR_TO_COLLECTION = _MIGRATION._SB_CHAR_TO_COLLECTION  # noqa: SLF001
_COLLECTION_TO_CHAR = _MIGRATION._SB_COLLECTION_TO_CHAR  # noqa: SLF001

_bg_char_to_collection = _MIGRATION.browser_default_flag_char_to_collection
_bg_collection_to_char = _MIGRATION.browser_default_flag_collection_to_char
_BG_CHAR_TO_COLLECTION = _MIGRATION._BG_CHAR_TO_COLLECTION  # noqa: SLF001
_BG_KEY = _MIGRATION._BROWSER_DEFAULT_COLLECTION_KEY  # noqa: SLF001


def _v4(response):
    body = response.json()
    return body["data"] if isinstance(body, dict) and "data" in body else body


class SettingsCollectionFlipTestCase(TestCase):
    """Char wire ↔ collection storage for browser settings."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.user = User.objects.create_user(username="flip", password=_TEST_PASSWORD)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _browser_row(self) -> SettingsBrowser:
        return SettingsBrowser.objects.select_related("show", "last_route").get(
            user=self.user
        )

    def test_show_collection_wire_stores_collection_columns(self) -> None:
        """PATCH collection ``show`` → collection GET; DB row holds the flags."""
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(
                {
                    "show": {
                        "publishers": True,
                        "imprints": True,
                        "series": False,
                        "volumes": False,
                    }
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        show = _v4(self.client.get(_SETTINGS_URL))["show"]
        assert show == {
            "publishers": True,
            "imprints": True,
            "series": False,
            "volumes": False,
        }
        row = self._browser_row().show
        assert row.publishers is True
        assert row.imprints is True
        assert row.series is False
        assert row.volumes is False

    def test_top_group_collection_wire_stores_collection(self) -> None:
        """PATCH ``topCollection="series"`` → same GET; DB stores ``"series"``."""
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"topCollection": "series"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        assert _v4(self.client.get(_SETTINGS_URL))["topCollection"] == "series"
        assert self._browser_row().top_collection == "series"

    def test_defaults_store_collection_and_no_root_zero(self) -> None:
        """A fresh row defaults to collection values on the migrated schema."""
        # Touch settings so the row + its related rows are created.
        assert self.client.get(_SETTINGS_URL).status_code == _HTTP_OK
        row = self._browser_row()
        last_route = row.last_route  # ty: ignore[unresolved-attribute]  # pyright: ignore[reportAttributeAccessIssue]
        # Model defaults are now collection values.
        assert row.top_collection == "publishers"
        assert last_route.collection == "root"
        # The dummy 0 root sentinel is gone from stored pks.
        assert 0 not in (last_route.pks or [])


class MigrationTableColumnsRemapTestCase(TestCase):
    """0043 remaps ``table_columns`` keys char<->collection (saved views kept)."""

    def test_char_keys_to_collections(self) -> None:
        """Legacy single-char top-collection keys flip to collection names."""
        remapped = _remap_table_columns_keys(
            {"c": ["issue"], "p": ["name"]}, _CHAR_TO_COLLECTION
        )
        assert remapped == {"comics": ["issue"], "publishers": ["name"]}

    def test_collection_keys_pass_through(self) -> None:
        """Already-migrated keys are left untouched (idempotent)."""
        original = {"series": ["name"], "volumes": ["issue"]}
        assert _remap_table_columns_keys(original, _CHAR_TO_COLLECTION) == original

    def test_empty_and_none_unchanged(self) -> None:
        """Falsy values short-circuit without raising."""
        assert _remap_table_columns_keys({}, _CHAR_TO_COLLECTION) == {}
        assert _remap_table_columns_keys(None, _CHAR_TO_COLLECTION) is None

    def test_reverse_collections_to_chars(self) -> None:
        """The reverse map restores the single-char dialect."""
        remapped = _remap_table_columns_keys(
            {"comics": ["issue"], "publishers": ["name"]}, _COLLECTION_TO_CHAR
        )
        assert remapped == {"c": ["issue"], "p": ["name"]}


class _FakeRow:
    """Stand-in SettingsBrowser row recording its ``save(update_fields=...)``."""

    def __init__(self, top_group, table_columns, name="") -> None:
        self.top_group = top_group
        self.table_columns = table_columns
        self.name = name
        self.saved_fields: list | None = None

    def save(self, update_fields=None) -> None:
        self.saved_fields = list(update_fields or [])


class _FakeManager:
    """Minimal ``objects`` manager exposing ``all().iterator()``."""

    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self

    def iterator(self):
        return iter(self._rows)


class _FakeModel:
    """Minimal model exposing ``.objects`` for the migration helper."""

    def __init__(self, rows) -> None:
        self.objects = _FakeManager(rows)


class MigrationBrowserRowWiringTestCase(TestCase):
    """``_sb_migrate_browser_rows`` flips top_group + table_columns for every row."""

    def test_active_and_saved_view_rows_migrated(self) -> None:
        """Both the active row and a named Saved View are remapped + saved."""
        active = _FakeRow("p", {"c": ["issue"]}, name="")
        saved = _FakeRow("s", {"p": ["name"]}, name="My View")
        model = _FakeModel([active, saved])

        _sb_migrate_browser_rows(model, _CHAR_TO_COLLECTION)

        assert active.top_group == "publishers"
        assert active.table_columns == {"comics": ["issue"]}
        assert set(active.saved_fields or []) == {"top_group", "table_columns"}
        # The Saved View's per-collection columns are preserved (remapped).
        assert saved.top_group == "series"
        assert saved.table_columns == {"publishers": ["name"]}
        assert set(saved.saved_fields or []) == {"top_group", "table_columns"}

    def test_already_collection_row_not_saved(self) -> None:
        """A row already on the collection vocabulary triggers no write."""
        row = _FakeRow("publishers", {"comics": ["issue"]})
        model = _FakeModel([row])
        _sb_migrate_browser_rows(model, _CHAR_TO_COLLECTION)
        assert row.saved_fields is None


class BrowserDefaultFlagMigrationTestCase(TestCase):
    """0043 flips the ``BG`` (Default View) admin flag value char<->collection."""

    @staticmethod
    def _set_bg(value) -> None:
        AdminFlag.objects.update_or_create(
            key=_BG_KEY, defaults={"on": True, "value": value}
        )

    @staticmethod
    def _bg_value() -> str:
        return AdminFlag.objects.get(key=_BG_KEY).value

    def test_every_char_maps_to_its_collection(self) -> None:
        """Each legacy top-group char (e.g. ``"p"``) flips to its collection."""
        for char, collection in _BG_CHAR_TO_COLLECTION.items():
            self._set_bg(char)
            _bg_char_to_collection(django_apps, None)
            assert self._bg_value() == collection

    def test_reverse_restores_char(self) -> None:
        """The reverse move restores the single-char dialect."""
        for char, collection in _BG_CHAR_TO_COLLECTION.items():
            self._set_bg(collection)
            _bg_collection_to_char(django_apps, None)
            assert self._bg_value() == char

    def test_already_collection_value_unchanged(self) -> None:
        """An already-migrated collection value is left untouched (idempotent)."""
        self._set_bg("publishers")
        _bg_char_to_collection(django_apps, None)
        assert self._bg_value() == "publishers"

    def test_unknown_value_unchanged(self) -> None:
        """A value outside the legacy char map (e.g. the empty default) is kept."""
        self._set_bg("")
        _bg_char_to_collection(django_apps, None)
        assert self._bg_value() == ""

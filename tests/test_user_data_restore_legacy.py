"""Restore's row builders, fed rows shaped like older sidecars."""

import json
from typing import Final

from django.contrib.auth.models import User
from django.test import TestCase

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105


class LegacyKeyRenameTests(TestCase):
    """
    Sidecars from before 0048 carry critical_rating; restore remaps it.

    Exercises the private helpers directly: rebuilding a whole
    legacy-schema sidecar for one column rename buys nothing over
    feeding the helpers legacy-shaped rows.
    """

    @staticmethod
    def _browser_row(**overrides) -> dict:
        row = {
            "top_collection": "publishers",
            "order_by": "critical_rating",
            "order_reverse": 1,
            "order_extra_keys": "[]",
            "search": "",
            # Retired sidecar columns; restore must ignore them.
            "custom_covers": 1,
            "dynamic_covers": 1,
            "twenty_four_hour_time": 0,
            "always_show_filename": 0,
            "view_mode": "",
            "table_columns": '{"critical_rating": true, "issue": true}',
            "table_cover_size": "",
        }
        row.update(overrides)
        return row

    def test_browser_defaults_remap_legacy_keys(self) -> None:
        """Legacy order_by values and table_columns keys map to community."""
        from codex.user_data.restore import _build_browser_defaults

        defaults = _build_browser_defaults(self._browser_row(), show=None)
        assert defaults["order_by"] == "community_rating"
        assert defaults["table_columns"] == {"community_rating": True, "issue": True}

    def test_site_defaults_rename_the_favorite_sort_and_column(self) -> None:
        """
        A pre-shelves backup's site defaults sort and show ``shelved``.

        The per-user rows were renamed; the site defaults kept a
        ``favorite`` sort nothing understands and dropped the column.
        """
        from codex.user_data.restore import _build_settings_defaults

        row = {
            "order_by": "favorite",
            "table_columns": '{"comics": ["issue", "favorite"]}',
        }
        defaults = _build_settings_defaults(row)
        assert defaults["order_by"] == "shelved"
        assert defaults["table_columns"]["comics"] == ["issue", "shelved"]

    def test_browser_defaults_pass_current_keys_through(self) -> None:
        """Current-name rows restore unchanged."""
        from codex.user_data.restore import _build_browser_defaults

        row = self._browser_row(
            order_by="community_rating", table_columns='{"community_rating": true}'
        )
        defaults = _build_browser_defaults(row, show=None)
        assert defaults["order_by"] == "community_rating"
        assert defaults["table_columns"] == {"community_rating": True}

    def test_browser_defaults_restore_collection_order_memory(self) -> None:
        """The per-collection sort memory round-trips out of the sidecar."""
        from codex.user_data.restore import _build_browser_defaults

        memory = {
            "comics": {
                "order_by": "created_at",
                "order_reverse": True,
                "order_extra_keys": [],
            }
        }
        row = self._browser_row(collection_order_memory=json.dumps(memory))
        defaults = _build_browser_defaults(row, show=None)
        assert defaults["collection_order_memory"] == memory

    def test_browser_defaults_remap_retired_sort_key(self) -> None:
        """A sidecar's retired alternate_number sort restores as reprints."""
        # It lives in three places, and settings load without
        # re-validation, so any one left behind reaches ORDER BY.
        from codex.user_data.restore import _build_browser_defaults

        row = self._browser_row(
            order_by="alternate_number",
            order_extra_keys=json.dumps([{"key": "alternate_number", "reverse": True}]),
            collection_order_memory=json.dumps(
                {
                    "comics": {
                        "order_by": "alternate_number",
                        "order_reverse": False,
                        "order_extra_keys": [
                            {"key": "alternate_number", "reverse": False}
                        ],
                    }
                }
            ),
        )
        defaults = _build_browser_defaults(row, show=None)
        assert defaults["order_by"] == "reprints"
        assert defaults["order_extra_keys"] == [{"key": "reprints", "reverse": True}]
        assert defaults["collection_order_memory"] == {
            "comics": {
                "order_by": "reprints",
                "order_reverse": False,
                "order_extra_keys": [{"key": "reprints", "reverse": False}],
            }
        }

    def test_browser_defaults_dedupe_retired_sort_key(self) -> None:
        """A sidecar carrying both the retired key and its replacement keeps one."""
        from codex.user_data.restore import _build_browser_defaults

        row = self._browser_row(
            order_extra_keys=json.dumps(
                [
                    {"key": "reprints", "reverse": False},
                    {"key": "alternate_number", "reverse": True},
                ]
            )
        )
        defaults = _build_browser_defaults(row, show=None)
        assert defaults["order_extra_keys"] == [{"key": "reprints", "reverse": False}]

    def test_browser_defaults_tolerate_missing_order_memory(self) -> None:
        """A sidecar written before the column existed restores empty."""
        from codex.user_data.restore import _build_browser_defaults

        defaults = _build_browser_defaults(self._browser_row(), show=None)
        assert defaults["collection_order_memory"] == {}

    def test_filter_restore_reads_legacy_column(self) -> None:
        """A legacy critical_rating filter column lands on community_rating."""
        from codex.models.settings import (
            SettingsBrowser,
            SettingsBrowserFilters,
            SettingsBrowserShow,
        )
        from codex.user_data.restore import RestoreReport, _restore_one_filter

        user = User.objects.create_user(username="filt", password=_TEST_PASSWORD)
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(user=user, show=show)
        # A legacy sidecar row: critical_rating column, no community_rating.
        row = {"bookmark": "", "favorite": 0, "critical_rating": "[4.5]"}
        _restore_one_filter(row, browser, RestoreReport())
        filters = SettingsBrowserFilters.objects.get(browser=browser)
        assert filters.community_rating == [4.5]


class TaggingDefaultsRestoreTests(TestCase):
    """A sidecar predating metron_key must still restore."""

    @staticmethod
    def _row(**overrides) -> dict:
        row = {
            "default_match_mode": "auto",
            "default_prompts_mode": "ask",
            "default_formats": '["COMIC_INFO"]',
            "default_sources": '["metron"]',
            "delete_original": 0,
            "metron_key": "token",
            "comicvine_key": "",
            "comicvine_url": "",
            "versedb_key": "versedb-token",
        }
        row.update(overrides)
        return row

    def test_metron_key_round_trips(self) -> None:
        from codex.user_data.restore import _build_tagging_defaults

        defaults = _build_tagging_defaults(self._row())
        assert defaults["metron_key"] == "token"

    def test_sidecar_without_metron_key_restores(self) -> None:
        """The column is simply absent in older backups; the default stands."""
        from codex.user_data.restore import _build_tagging_defaults

        row = self._row()
        del row["metron_key"]
        defaults = _build_tagging_defaults(row)
        assert "metron_key" not in defaults
        assert defaults["default_match_mode"] == "auto"

    def test_versedb_key_round_trips(self) -> None:
        from codex.user_data.restore import _build_tagging_defaults

        defaults = _build_tagging_defaults(self._row())
        assert defaults["versedb_key"] == "versedb-token"

    def test_sidecar_without_versedb_key_restores(self) -> None:
        """A backup from before VerseDB has no such column; the default stands."""
        from codex.user_data.restore import _build_tagging_defaults

        row = self._row()
        del row["versedb_key"]
        defaults = _build_tagging_defaults(row)
        assert "versedb_key" not in defaults
        assert defaults["metron_key"] == "token"

    def test_comicvine_url_round_trips(self) -> None:
        from codex.user_data.restore import _build_tagging_defaults

        defaults = _build_tagging_defaults(
            self._row(comicvine_url="https://cv.example.com/api")
        )
        assert defaults["comicvine_url"] == "https://cv.example.com/api"

    def test_a_retired_metron_url_column_is_ignored(self) -> None:
        """Sidecars predating the removal carry a column the model dropped."""
        from codex.user_data.restore import _build_tagging_defaults

        defaults = _build_tagging_defaults(
            self._row(metron_url="https://metron.example.com")
        )
        assert "metron_url" not in defaults

    def test_a_retired_metron_login_is_ignored(self) -> None:
        """Sidecars from before Metron took only a key carry its login columns."""
        from codex.user_data.restore import _build_tagging_defaults

        defaults = _build_tagging_defaults(
            self._row(metron_user="u", metron_password="p")  # noqa: S106
        )
        assert "metron_user" not in defaults
        assert "metron_password" not in defaults
        assert defaults["metron_key"] == "token"

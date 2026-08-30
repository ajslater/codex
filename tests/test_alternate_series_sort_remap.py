"""
0054 remaps the retired ``alternate_number`` sort key onto ``reprints``.

The key lived in three places on ``SettingsBrowser`` — the ``order_by``
column, the ``order_extra_keys`` list and the per-top-collection
``collection_order_memory`` map. Stored settings load without
re-validation, so anything the migration misses reaches ORDER BY and
raises. Runs the migration's helper against live models: every surface
it touches still exists post-migration.
"""

import importlib
from typing import Final

from django.apps import apps
from django.test import TestCase

from codex.models.settings import SettingsBrowser, SettingsBrowserShow

_MIGRATION = importlib.import_module(
    "codex.migrations.0054_merge_alternate_number_sort"
)
_remap_browser_settings = _MIGRATION._remap_browser_settings  # noqa: SLF001

_OLD: Final = "alternate_number"
_NEW: Final = "reprints"


class Migration0054RemapTestCase(TestCase):
    """The retired sort key is rewritten everywhere it can be stored."""

    @staticmethod
    def _make_row(**overrides) -> SettingsBrowser:
        show, _ = SettingsBrowserShow.objects.get_or_create()
        fields = {
            "show": show,
            "order_by": "sort_name",
            "order_extra_keys": [],
            "collection_order_memory": {},
        }
        fields.update(overrides)
        return SettingsBrowser.objects.create(**fields)

    def test_order_by_column_remapped(self) -> None:
        """The plain sort key moves over; other rows are left alone."""
        remapped = self._make_row(order_by=_OLD)
        untouched = self._make_row(order_by="sort_name")

        _remap_browser_settings(apps, None)

        remapped.refresh_from_db()
        untouched.refresh_from_db()
        assert remapped.order_by == _NEW
        assert untouched.order_by == "sort_name"

    def test_extra_sort_keys_remapped(self) -> None:
        """A multi-sort extra on the retired key moves over, keeping its direction."""
        row = self._make_row(
            order_extra_keys=[
                {"key": "sort_name", "reverse": False},
                {"key": _OLD, "reverse": True},
            ]
        )

        _remap_browser_settings(apps, None)

        row.refresh_from_db()
        assert row.order_extra_keys == [
            {"key": "sort_name", "reverse": False},
            {"key": _NEW, "reverse": True},
        ]

    def test_extra_sort_keys_dedupe(self) -> None:
        """A row already sorting by reprints doesn't end up with it twice."""
        # One column can only carry one sort, so the first wins.
        row = self._make_row(
            order_extra_keys=[
                {"key": _NEW, "reverse": False},
                {"key": _OLD, "reverse": True},
            ]
        )

        _remap_browser_settings(apps, None)

        row.refresh_from_db()
        assert row.order_extra_keys == [{"key": _NEW, "reverse": False}]

    def test_collection_order_memory_remapped(self) -> None:
        """The per-top-collection sort memory is rewritten too."""
        # Missed here, the dead key gets re-injected into params the
        # next time the user switches back to that top collection.
        row = self._make_row(
            collection_order_memory={
                "comics": {
                    "order_by": _OLD,
                    "order_reverse": True,
                    "order_extra_keys": [{"key": _OLD, "reverse": False}],
                },
                "folders": {
                    "order_by": "sort_name",
                    "order_reverse": False,
                    "order_extra_keys": [],
                },
            }
        )

        _remap_browser_settings(apps, None)

        row.refresh_from_db()
        assert row.collection_order_memory == {
            "comics": {
                "order_by": _NEW,
                "order_reverse": True,
                "order_extra_keys": [{"key": _NEW, "reverse": False}],
            },
            "folders": {
                "order_by": "sort_name",
                "order_reverse": False,
                "order_extra_keys": [],
            },
        }

    def test_saved_views_remapped(self) -> None:
        """Saved views are more rows in the same table and get the same pass."""
        saved = self._make_row(name="A Saved View", order_by=_OLD)

        _remap_browser_settings(apps, None)

        saved.refresh_from_db()
        assert saved.order_by == _NEW

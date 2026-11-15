"""
Tests for migration 0061, which folds favorites into shelves.

The forward data step needs the ``Favorite`` table and the ``favorite``
filter column, neither of which exists in the current schema, so these
run the real migration both ways: back to 0060 to seed the old shape,
then forward to 0061 to check what it became. The backward leg doubles
as the test of the reverse data step.
"""

from typing import Final, override

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

_BEFORE: Final = [("codex", "0060_koreader_sync")]
_AFTER: Final = [("codex", "0061_shelves")]
_SERIES_PK: Final = 11
_COMIC_PK: Final = 22
_FAVORITE_COUNT: Final = 2


def _migrate(target):
    """Migrate to ``target`` and return the app registry at that state."""
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return MigrationExecutor(connection).loader.project_state(target).apps


class ShelvesMigrationTests(TransactionTestCase):
    """Favorites, their filter and their sort key all carry over."""

    @override
    def setUp(self) -> None:
        self.addCleanup(_migrate, _AFTER)
        self.fan = User.objects.create(username="fan")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.plain = User.objects.create(username="plain")  # pyright: ignore[reportUninitializedInstanceVariable]

    def _settings_row(self, apps, user, name: str, **fields):
        show, _ = apps.get_model("codex", "SettingsBrowserShow").objects.get_or_create()
        return apps.get_model("codex", "SettingsBrowser").objects.create(
            user_id=user.pk, show=show, name=name, **fields
        )

    def _seed_old_shape(self, apps) -> None:
        favorite = apps.get_model("codex", "Favorite")
        filters = apps.get_model("codex", "SettingsBrowserFilters")
        favorite.objects.create(
            user_id=self.fan.pk, collection="series", target_id=_SERIES_PK
        )
        favorite.objects.create(
            user_id=self.fan.pk, collection="comics", target_id=_COMIC_PK
        )
        # The fan's live row and a saved view both filter on favorites and
        # sort by the favorite flag everywhere a sort key can be stored.
        for name in ("", "starred"):
            row = self._settings_row(
                apps,
                self.fan,
                name,
                order_by="favorite",
                order_extra_keys=[{"key": "favorite", "reverse": True}],
                collection_order_memory={
                    "series": {"order_by": "favorite", "order_extra_keys": []}
                },
                table_columns={"comics": ["issue", "favorite"]},
            )
            filters.objects.create(browser=row, favorite=True)
        # A user with the filter on but nothing favorited.
        filters.objects.create(
            browser=self._settings_row(apps, self.plain, ""), favorite=True
        )

    def _assert_forward(self, new_apps) -> None:
        """Favorites are on one shelf; filters and sort keys point at it."""
        shelf_model = new_apps.get_model("codex", "Shelf")
        item_model = new_apps.get_model("codex", "ShelfItem")
        filters = new_apps.get_model("codex", "SettingsBrowserFilters")
        # One shelf, for the user who had favorites, and none for the other.
        shelves = list(shelf_model.objects.values("pk", "user_id", "name"))
        assert [(row["user_id"], row["name"]) for row in shelves] == [
            (self.fan.pk, "Favorites")
        ]
        shelf_pk = shelves[0]["pk"]
        assert set(
            item_model.objects.filter(shelf_id=shelf_pk).values_list(
                "collection", "target_id"
            )
        ) == {("series", _SERIES_PK), ("comics", _COMIC_PK)}

        fan_filters = filters.objects.filter(browser__user_id=self.fan.pk)
        assert list(fan_filters.values_list("shelves", flat=True)) == [
            [shelf_pk],
            [shelf_pk],
        ]
        plain_filters = filters.objects.filter(browser__user_id=self.plain.pk)
        assert list(plain_filters.values_list("shelves", flat=True)) == [[]]
        self._assert_sort_keys_renamed(new_apps)

    def _assert_sort_keys_renamed(self, new_apps) -> None:
        """Every stored ``favorite`` sort key and column became ``shelved``."""
        settings_browser = new_apps.get_model("codex", "SettingsBrowser")
        fan_settings = settings_browser.objects.filter(user_id=self.fan.pk).values(
            "order_by", "order_extra_keys", "collection_order_memory", "table_columns"
        )
        assert len(fan_settings) == _FAVORITE_COUNT
        for row in fan_settings:
            assert row["order_by"] == "shelved"
            assert row["order_extra_keys"] == [{"key": "shelved", "reverse": True}]
            assert row["collection_order_memory"]["series"]["order_by"] == "shelved"
            assert row["table_columns"] == {"comics": ["issue", "shelved"]}

    def _assert_reverse(self, old_apps) -> None:
        """Only the Favorites shelf comes back, as favorites."""
        favorite = old_apps.get_model("codex", "Favorite")
        assert favorite.objects.count() == _FAVORITE_COUNT
        assert set(favorite.objects.values_list("user_id", flat=True)) == {self.fan.pk}
        old_filters = old_apps.get_model("codex", "SettingsBrowserFilters")
        assert set(
            old_filters.objects.filter(browser__user_id=self.fan.pk).values_list(
                "favorite", flat=True
            )
        ) == {True}
        assert list(
            old_filters.objects.filter(browser__user_id=self.plain.pk).values_list(
                "favorite", flat=True
            )
        ) == [False]
        old_settings = old_apps.get_model("codex", "SettingsBrowser")
        assert set(
            old_settings.objects.filter(user_id=self.fan.pk).values_list(
                "order_by", flat=True
            )
        ) == {"favorite"}

    def test_favorites_become_a_shelf_and_back(self):
        """Forward builds the Favorites shelf; reverse restores favorites."""
        old_apps = _migrate(_BEFORE)
        self._seed_old_shape(old_apps)

        new_apps = _migrate(_AFTER)
        self._assert_forward(new_apps)

        # A second, differently named shelf does not survive the reverse.
        other = new_apps.get_model("codex", "Shelf").objects.create(
            user_id=self.plain.pk, name="Later"
        )
        new_apps.get_model("codex", "ShelfItem").objects.create(
            shelf=other, collection="series", target_id=1
        )

        self._assert_reverse(_migrate(_BEFORE))

"""
The reading lists browser filter: comics in the lists the viewer may see.

Another user's personal list is never a choice, never matches when its pk
is sent anyway, and never makes a comic count as "in a list" for the None
choice. Saved filters keep their lists across a backup by uuid.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.choices.browser import DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.models.settings import (
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserShow,
)
from codex.user_data.restore import RestoreReport, _restore_one_filter
from codex.user_data.serializers import serialize_settings_filters
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_SHOW_ALL: Final = {
    "publishers": True,
    "imprints": True,
    "series": True,
    "volumes": True,
}


class _ListsFixture(ReadingListFixture):
    """A global list of two comics and another user's list of the others."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.owner = User.objects.create_user(username="owner", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other = User.objects.create_user(username="other", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.secret = self._list("Secret", self.comics[2:], user=self.owner)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.shared = self._list("Shared", self.comics[:2])  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.other)

    @staticmethod
    def _list(name: str, comics, user=None) -> ReadingList:
        reading_list = ReadingList.objects.create(name=name, user=user)
        for position, comic in enumerate(comics):
            ReadingListEntry.objects.create(
                reading_list=reading_list,
                position=position,
                comic=comic,
                match_tier=ReadingListMatchTier.MANUAL,
            )
        return reading_list


class ReadingListFilterTests(_ListsFixture):
    """Filter comics by reading list, over visible lists only."""

    def _books(self, reading_lists: list) -> list[int]:
        params = {
            "filters": json.dumps({"readingLists": reading_lists}),
            "search": "",
            "show": json.dumps(_SHOW_ALL),
            "view_mode": "cover",
        }
        volume_pk = self.comics[0].volume_id
        response = self.client.get(f"/api/v4/browse/volumes/{volume_pk}", params)
        assert response.status_code == _OK, response.content
        return [book["pk"] for book in response.json()["data"]["books"]]

    def _choices(self, field: str = "") -> dict:
        params = {"filters": json.dumps({}), "search": ""}
        suffix = f"/{field}" if field else ""
        response = self.client.get(f"/api/v4/browse/series/0/choices{suffix}", params)
        assert response.status_code == _OK, response.content
        return response.json()["data"]

    def test_a_visible_list_filters_its_comics(self) -> None:
        """Filtering by the global list shows only its comics."""
        assert self._books([self.shared.pk]) == [
            self.comics[0].pk,
            self.comics[1].pk,
        ]

    def test_another_users_list_matches_nothing(self) -> None:
        """A personal list's pk sent by another user filters to nothing."""
        assert self._books([self.secret.pk]) == []

    def test_none_is_in_no_visible_list(self) -> None:
        """The None choice holds the comics outside every visible list."""
        books = self._books([VUETIFY_NULL_CODE])
        assert books == [self.comics[2].pk, self.comics[3].pk]

    def test_owner_filters_by_own_list(self) -> None:
        """The owner may filter by their own list."""
        self.client.force_login(self.owner)
        assert self._books([self.secret.pk]) == [
            self.comics[2].pk,
            self.comics[3].pk,
        ]

    def test_choices_name_only_visible_lists(self) -> None:
        """The filter offers the global list and None, never the private one."""
        assert self._choices()["readingLists"] is True
        choices = self._choices("readingLists")["choices"]
        assert [choice["name"] for choice in choices] == [DUMMY_NULL_NAME, "Shared"]

    def test_owner_choices_include_own_list(self) -> None:
        """The owner sees both lists and no None: every comic is listed."""
        self.client.force_login(self.owner)
        choices = self._choices("readingLists")["choices"]
        assert [choice["name"] for choice in choices] == ["Secret", "Shared"]


class ReadingListFilterSidecarTests(_ListsFixture):
    """A saved reading lists filter survives a backup by uuid."""

    def _filters(self, user, reading_lists: list) -> SettingsBrowserFilters:
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser, _ = SettingsBrowser.objects.get_or_create(user=user, show=show)
        filters, _ = SettingsBrowserFilters.objects.update_or_create(
            browser=browser, defaults={"reading_lists": reading_lists}
        )
        return filters

    def test_round_trip_by_uuid(self) -> None:
        """Pks become uuids and back; another user's list drops out."""
        filters = self._filters(self.other, [self.shared.pk, self.secret.pk])
        dumped = serialize_settings_filters(filters)
        assert dumped is not None
        row = dumped[2]
        assert json.loads(row["reading_lists"]) == [str(self.shared.uuid)]
        filters.reading_lists = []
        filters.save()
        _restore_one_filter(row, filters.browser, RestoreReport())
        filters.refresh_from_db()
        assert filters.reading_lists == [self.shared.pk]

    def test_an_older_sidecar_restores_no_lists(self) -> None:
        """A row from before the column restores an empty filter."""
        filters = self._filters(self.owner, [self.secret.pk])
        _restore_one_filter({"bookmark": ""}, filters.browser, RestoreReport())
        filters.refresh_from_db()
        assert filters.reading_lists == []

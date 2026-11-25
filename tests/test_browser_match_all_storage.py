"""
The Any/All switch's setting: ``match_all``, the filters set to All.

One filter setting holding the names of the tag-like filters to match
all ticked values in. Its items are filter names, which the API spells
in camelCase like every filter key; the server stores snake_case. It is
not a filter of comics: on its own it narrows nothing and does not hide
a list's missing issues.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Final

from django.contrib.auth.models import User
from django.core.cache import cache

from codex.choices.browser import BROWSER_CHOICES, BROWSER_MATCH_ALL_FILTERS
from codex.models import ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.models.settings import (
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserShow,
)
from codex.user_data.restore import restore
from codex.views.browser.const import BROWSER_FILTER_KEYS
from codex.views.browser.filters.field import _FILTER_REL_MAP, ComicFieldFilterView
from codex.views.browser.filters.reading_lists import (
    READING_LIST_KIND_FILTER,
    READING_LISTS_FILTER,
)
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_filter_items import FilterFixture
from tests.test_user_data_restore import _TEST_PASSWORD, _SidecarRestoreCase

if TYPE_CHECKING:
    from pathlib import Path

_OK: Final = 200
_BAD: Final = 400
_SETTINGS: Final = "/api/v4/browse/publishers/settings"
_WIRE: Final = ["characters", "seriesGroups", "identifierSource", "readingLists"]
_STORED: Final = ["characters", "series_groups", "identifier_source", "reading_lists"]


def test_the_tag_like_filters_are_those_a_comic_holds_several_of() -> None:
    """The one list, checked against the model, plus the Reading Lists filter."""
    by_model = {
        key
        for key in BROWSER_FILTER_KEYS
        if key not in (READING_LISTS_FILTER, READING_LIST_KIND_FILTER)
        and ComicFieldFilterView._is_multivalued(_FILTER_REL_MAP.get(key, key))  # noqa: SLF001
    }
    assert set(BROWSER_MATCH_ALL_FILTERS) == {*by_model, READING_LISTS_FILTER}


def test_the_frontend_gets_them_in_its_own_spelling() -> None:
    """Exported by make build-choices in camelCase, like the filter keys."""
    exported = BROWSER_CHOICES["MATCH_ALL_FILTERS"]
    assert isinstance(exported, tuple)
    assert {"seriesGroups", "identifierSource", "readingLists"} <= set(exported)
    assert len(exported) == len(BROWSER_MATCH_ALL_FILTERS)


class MatchAllWireTests(FilterFixture):
    """The names cross the API in camelCase and are stored in snake_case."""

    def _stored(self) -> list[str]:
        return SettingsBrowserFilters.objects.get(browser__user=self.reader).match_all

    def _browse_response(self, filters: dict):
        params = {"filters": json.dumps(filters), "search": ""}
        return self.client.get("/api/v4/browse/series", params)

    def test_a_browse_saves_the_names(self) -> None:
        """Two-word names convert at the boundary."""
        self.browse("series", {"matchAll": _WIRE}, top="series")
        assert self._stored() == _STORED

    def test_the_settings_give_them_back_in_camel_case(self) -> None:
        """The stored snake_case names leave in the API's spelling."""
        self.browse("series", {"matchAll": _WIRE}, top="series")
        response = self.client.get(_SETTINGS)
        assert response.status_code == _OK, response.content
        assert response.json()["data"]["filters"]["matchAll"] == _WIRE

    def test_the_settings_save_takes_them(self) -> None:
        """The settings PATCH takes the same spelling."""
        response = self.client.patch(
            _SETTINGS,
            data=json.dumps({"filters": {"matchAll": ["seriesGroups"]}}),
            content_type="application/json",
        )
        assert response.status_code == _OK, response.content
        assert self._stored() == ["series_groups"]

    def test_a_single_valued_filter_is_refused(self) -> None:
        """A comic has one year: All means nothing there."""
        assert self._browse_response({"matchAll": ["year"]}).status_code == _BAD

    def test_the_server_spelling_is_refused(self) -> None:
        """One spelling on the wire."""
        response = self._browse_response({"matchAll": ["series_groups"]})
        assert response.status_code == _BAD

    def test_an_unknown_name_is_refused(self) -> None:
        """Only filter names."""
        assert self._browse_response({"matchAll": ["everything"]}).status_code == _BAD

    def test_it_narrows_nothing_on_its_own(self) -> None:
        """Set to All with nothing ticked: every comic."""
        everything = self.listed({})
        assert self.listed({"matchAll": ["characters"]}) == everything


class MatchAllMissingIssuesTests(FilterFixture):
    """The switch is no filter: a list's missing issues still show."""

    def test_missing_issues_show_with_the_switch_on(self) -> None:
        add_comics(self.mine, [self.comics[0].pk])
        ReadingListEntry.objects.create(
            reading_list=self.mine,
            position=1,
            comic=None,
            series_name="Tie-In",
            issue="1",
            match_tier=ReadingListMatchTier.NONE,
        )
        cache.clear()
        params = {
            "order_by": "story_arc_number",
            "order_reverse": "false",
            "filters": json.dumps({"matchAll": ["characters"]}),
        }
        response = self.client.get(f"/api/v4/browse/arcs/{self.mine.pk}", params)
        assert response.status_code == _OK, response.content
        missing = response.json()["data"].get("missingEntries") or ()
        assert [entry["seriesName"] for entry in missing] == ["Tie-In"]


class MatchAllBackupTests(_SidecarRestoreCase):
    """A backup keeps the switch; unknown names drop on restore."""

    def _snapshot(self, match_all: list[str]) -> tuple[User, Path]:
        user = User.objects.create_user(username="alice", password=_TEST_PASSWORD)
        show, _ = SettingsBrowserShow.objects.get_or_create()
        browser = SettingsBrowser.objects.create(user=user, show=show)
        SettingsBrowserFilters.objects.create(browser=browser, match_all=match_all)
        snapshot = self._snapshot_sidecar()
        SettingsBrowser.objects.all().delete()
        return user, snapshot

    @staticmethod
    def _restored(user: User, snapshot: Path) -> list[str]:
        restore(sidecar_path=snapshot)
        return SettingsBrowserFilters.objects.get(browser__user=user).match_all

    def test_round_trip(self) -> None:
        """Stored names come back as they were."""
        user, snapshot = self._snapshot(["characters", "series_groups"])
        assert self._restored(user, snapshot) == ["characters", "series_groups"]

    def test_unknown_names_drop(self) -> None:
        """A name that is not a tag-like filter is left out."""
        user, snapshot = self._snapshot([])
        with sqlite3.connect(snapshot) as conn:
            conn.execute(
                "UPDATE settings_filters SET match_all = ?",
                ('["characters", "year", "bogus", "characters"]',),
            )
        assert self._restored(user, snapshot) == ["characters"]

    def test_a_backup_without_the_switch_restores(self) -> None:
        """A backup from before the switch restores with every filter on Any."""
        user, snapshot = self._snapshot(["tags"])
        with sqlite3.connect(snapshot) as conn:
            conn.execute("ALTER TABLE settings_filters DROP COLUMN match_all")
        assert self._restored(user, snapshot) == []

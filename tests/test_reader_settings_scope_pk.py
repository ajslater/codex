"""
Reader settings for a scope only exist for something the reader may see.

``?reading_list_pk=`` was parsed with a bare ``int()``, so a non-number was
a 500. A PATCH made a settings row for any pk at all: another user's
personal list, or one that does not exist.
"""

import json
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.models.settings import SettingsReader
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_BAD_REQUEST: Final = 400
_NOT_FOUND: Final = 404
_MISSING_PK: Final = 999999


class ReaderSettingsScopePkTests(ReadingListFixture):
    """The arcs scope takes a visible list's pk, and only that."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.comic = self.comics[0]  # pyright: ignore[reportUninitializedInstanceVariable]
        self.shared = ReadingList.objects.create(name="Shared")  # pyright: ignore[reportUninitializedInstanceVariable]
        ReadingListEntry.objects.create(
            reading_list=self.shared,
            comic=self.comic,
            match_tier=ReadingListMatchTier.MANUAL,
        )
        other = User.objects.create_user(username="other", password=_PW)
        self.theirs = ReadingList.objects.create(name="Theirs", user=other)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(User.objects.create_user(username="u", password=_PW))
        self.url = f"/api/v4/comics/{self.comic.pk}/reader-settings"  # pyright: ignore[reportUninitializedInstanceVariable]

    def _patch(self, scope: str, scope_pk: int):
        return self.client.patch(
            self.url,
            data=json.dumps({"scope": scope, "scopePk": scope_pk, "fitTo": "H"}),
            content_type="application/json",
        )

    def test_a_non_numeric_list_pk_is_a_400(self) -> None:
        """A bad ``reading_list_pk`` is refused, not a server error."""
        response = self.client.get(
            self.url, {"scopes": "global,arcs", "reading_list_pk": "abc"}
        )
        assert response.status_code == _BAD_REQUEST, response.content

    def test_a_visible_list_takes_settings(self) -> None:
        """The list the comic is read from gets its own settings."""
        response = self._patch("arcs", self.shared.pk)
        assert response.status_code == _OK, response.content
        assert SettingsReader.objects.filter(reading_list=self.shared).exists()

    def test_another_users_list_takes_no_settings(self) -> None:
        """Another user's personal list is indistinguishable from none."""
        response = self._patch("arcs", self.theirs.pk)
        assert response.status_code == _NOT_FOUND, response.content
        assert not SettingsReader.objects.filter(reading_list=self.theirs).exists()

    def test_a_missing_list_takes_no_settings(self) -> None:
        """A pk that names no list is a 404."""
        response = self._patch("arcs", _MISSING_PK)
        assert response.status_code == _NOT_FOUND, response.content
        assert not SettingsReader.objects.filter(
            reading_list_id=_MISSING_PK
        ).exists()

    def test_a_missing_series_takes_no_settings(self) -> None:
        """The same holds for every scope with a pk."""
        response = self._patch("series", _MISSING_PK)
        assert response.status_code == _NOT_FOUND, response.content
        assert not SettingsReader.objects.filter(series_id=_MISSING_PK).exists()

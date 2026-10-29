"""
Two first requests for one session race to create its browser settings.

Both look the row up, both miss, both insert. The loser hit the unique
constraint and answered 500 (``UNIQUE constraint failed:
codex_settingsbrowser.session_id, ...``), most visibly on a new visitor's
first page load. The loser now uses the winner's row.

The race window is reproduced by letting the lookups miss once while the
winner's row already exists, as ``test_concurrent_create_does_not_raise``
does for the reader row.
"""

from importlib import import_module
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.db import IntegrityError
from django.test import RequestFactory
from rest_framework.request import Request

from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserLastRoute,
)
from codex.views.reader.params import ReaderParamsView
from codex.views.settings import (
    BROWSER_CREATE_ARGS,
    BROWSER_FILTER_ARGS,
    SettingsBaseView,
)
from tests.settings_defaults_helpers import TEST_PASSWORD, SettingsDefaultsCase

_LOOKUPS = ("_get_or_create_settings_user", "_get_or_create_settings_session")


def _view(user=None) -> ReaderParamsView:
    """Build a settings view on a fresh session, as a first request has."""
    request = RequestFactory().get("/")
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore()
    request.user = user or AnonymousUser()
    view = ReaderParamsView()
    view.request = Request(request)
    view.kwargs = {}
    return view


def _miss_once(name: str):
    """Patch a lookup to miss on its first call: the loser's view of the race."""
    original = getattr(SettingsBaseView, name)
    missed = []

    def lookup(*args):
        if not missed:
            missed.append(True)
            return None
        return original(*args)

    return patch.object(SettingsBaseView, name, side_effect=lookup)


def _get_browser_settings(view: ReaderParamsView) -> SettingsBrowser:
    row = view._get_or_create_settings(  # noqa: SLF001
        SettingsBrowser, ClientChoices.API, BROWSER_FILTER_ARGS, BROWSER_CREATE_ARGS
    )
    assert isinstance(row, SettingsBrowser)
    return row


class BrowserSettingsCreateRaceTestCase(SettingsDefaultsCase):
    """The request that loses the create race uses the winner's row."""

    def _assert_uses_the_winners_row(self, view: ReaderParamsView, user) -> None:
        session_key = view._ensure_session_key()  # noqa: SLF001
        winner = SettingsBaseView._create_browser_settings(  # noqa: SLF001
            user, session_key, ClientChoices.API, BROWSER_CREATE_ARGS
        )
        with _miss_once(_LOOKUPS[0]), _miss_once(_LOOKUPS[1]):
            row = _get_browser_settings(view)

        assert row.pk == winner.pk
        assert SettingsBrowser.objects.filter(session_id=session_key).count() == 1
        # The winner's related rows are there, and the loser left none behind.
        for related in (SettingsBrowserFilters, SettingsBrowserLastRoute):
            owners = related.objects.values_list("browser", flat=True)
            assert list(owners) == [winner.pk]

    def test_anonymous_session_race(self) -> None:
        self._assert_uses_the_winners_row(_view(), None)

    def test_user_race(self) -> None:
        user = User.objects.create_user(username="racer", password=TEST_PASSWORD)
        self._assert_uses_the_winners_row(_view(user), user)

    def test_a_real_integrity_error_still_raises(self) -> None:
        """Only a row someone else created is absorbed; nothing found re-raises."""
        view = _view()
        with (
            patch.object(
                SettingsBaseView,
                "_create_browser_settings",
                side_effect=IntegrityError("boom"),
            ),
            pytest.raises(IntegrityError),
        ):
            _get_browser_settings(view)

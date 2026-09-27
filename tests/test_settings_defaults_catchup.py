"""The Save-time catch-up for anonymous rows still at the old site default."""

import json
from http import HTTPStatus
from importlib import import_module
from typing import Any, Final, override
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import Imprint, Publisher, Series, SettingsDefaults
from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserLastRoute,
    SettingsBrowserShow,
    SettingsReader,
)
from codex.startup import init_admin_flags, init_settings_defaults, init_timestamps

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_URL: Final = "/api/v4/admin/settings-defaults"
_REACH_URL: Final = "/api/v4/admin/settings-defaults/reach"
_QUEUE: Final = "codex.views.admin.settings_defaults.LIBRARIAN_QUEUE"
_FACTORY_SHOW: Final = {
    "publishers": True,
    "imprints": False,
    "series": True,
    "volumes": False,
}


def _session_key() -> str:
    engine = import_module(settings.SESSION_ENGINE)
    store = engine.SessionStore()
    store.create()
    return store.session_key


def _browser(
    *,
    top: str = "publishers",
    show: dict | None = None,
    order_by: str = "",
    bookmark: str = "",
    route: tuple[str, tuple[int, ...], int] = ("root", (), 1),
    user: User | None = None,
    client: str = ClientChoices.API,
    name: str = "",
    **fields,
) -> SettingsBrowser:
    """Create one browser settings row with its related rows."""
    flags: dict[str, Any] = dict(show or _FACTORY_SHOW)
    show_row, _ = SettingsBrowserShow.objects.get_or_create(**flags)
    row = SettingsBrowser.objects.create(
        user=user,
        session_id=None if user else _session_key(),
        client=client,
        name=name,
        top_collection=top,
        order_by=order_by,
        show=show_row,
        **fields,
    )
    SettingsBrowserFilters.objects.create(browser=row, bookmark=bookmark)
    collection, pks, page = route
    SettingsBrowserLastRoute.objects.create(
        browser=row, collection=collection, pks=list(pks), page=page
    )
    return row


def _reload(row: SettingsBrowser) -> SettingsBrowser:
    return SettingsBrowser.objects.select_related("show", "filters", "last_route").get(
        pk=row.pk
    )


def _show(row: SettingsBrowser) -> dict:
    show = _reload(row).show
    return {key: getattr(show, key) for key in _FACTORY_SHOW}


class _CatchupCase(TestCase):
    """Seed startup rows, log in staff, and PUT with the catch-up flag."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        init_timestamps()
        init_settings_defaults()
        admin = User.objects.create_user(
            username="catchup-admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _put(self, payload: dict, *, apply: bool = True) -> dict:
        body = {**payload, "applyToAnonymous": apply}
        with patch(_QUEUE):
            response = self.client.put(
                _URL, data=json.dumps(body), content_type="application/json"
            )
        assert response.status_code == HTTPStatus.OK, response.content
        return response.json()["data"]


class CatchupFieldTestCase(_CatchupCase):
    """Each changed field moves the rows at its old value and no others."""

    def test_direct_fields(self) -> None:
        default = _browser()
        custom = _browser(order_by="created_at", view_mode="table")
        data = self._put(
            {
                "browser": {
                    "orderBy": "size",
                    "orderReverse": True,
                    "twentyFourHourTime": True,
                    "alwaysShowFilename": True,
                }
            }
        )
        default = _reload(default)
        assert default.order_by == "size"
        assert default.order_reverse is True
        assert default.twenty_four_hour_time is True
        assert default.always_show_filename is True
        custom = _reload(custom)
        assert custom.order_by == "created_at"
        assert custom.view_mode == "table"
        assert data["applied"]["orderBy"] == 1
        assert data["applied"]["orderReverse"] == 2  # noqa: PLR2004

    def test_view_mode(self) -> None:
        default = _browser()
        self._put({"browser": {"viewMode": "table"}})
        assert _reload(default).view_mode == "table"

    def test_automatic_sort_counts_as_untouched(self) -> None:
        moved = [
            _browser(order_by=""),
            _browser(order_by="sort_name"),
            _browser(top="folders", order_by="filename"),
            _browser(top="arcs", order_by="story_arc_number"),
        ]
        chosen = _browser(order_by="filename")
        self._put({"browser": {"orderBy": "created_at"}})
        for row in moved:
            assert _reload(row).order_by == "created_at", row.top_collection
        assert _reload(chosen).order_by == "filename"

    def test_bookmark(self) -> None:
        default = _browser()
        custom = _browser(bookmark="READ")
        data = self._put({"browser": {"bookmark": "UNREAD"}})
        assert _reload(default).filters.bookmark == "UNREAD"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        assert _reload(custom).filters.bookmark == "READ"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        assert data["applied"]["bookmark"] == 1

    def test_reader_globals(self) -> None:
        unseeded = SettingsReader.objects.create(
            session_id=_session_key(), client=ClientChoices.API
        )
        seeded = SettingsReader.objects.create(
            session_id=_session_key(),
            client=ClientChoices.API,
            fit_to="W",
            two_pages=False,
        )
        custom = SettingsReader.objects.create(
            session_id=_session_key(),
            client=ClientChoices.API,
            fit_to="O",
            two_pages=True,
        )
        self._put({"reader": {"fitTo": "H", "twoPages": True}})
        for row in (unseeded, seeded):
            row.refresh_from_db()
            assert row.fit_to == "H"
            assert row.two_pages is True
        custom.refresh_from_db()
        assert custom.fit_to == "O"


class CatchupScopeTestCase(_CatchupCase):
    """Only anonymous live API rows move, and only when asked."""

    def test_untouched_rows(self) -> None:
        user = User.objects.create_user(username="owner", password=_TEST_PASSWORD)
        saved_view = _browser(name="My View")
        user_row = _browser(user=user)
        opds_row = _browser(client=ClientChoices.OPDS)
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", imprint=imprint, publisher=publisher)
        scoped = SettingsReader.objects.create(
            session_id=_session_key(), client=ClientChoices.API, series=series
        )
        self._put({"browser": {"viewMode": "table"}, "reader": {"fitTo": "H"}})
        for row in (saved_view, user_row, opds_row):
            assert _reload(row).view_mode == "cover"
        scoped.refresh_from_db()
        assert scoped.fit_to == ""

    def test_flag_off_moves_nothing(self) -> None:
        default = _browser()
        reader = SettingsReader.objects.create(
            session_id=_session_key(), client=ClientChoices.API, fit_to="W"
        )
        data = self._put(
            {"browser": {"viewMode": "table"}, "reader": {"fitTo": "H"}}, apply=False
        )
        assert "applied" not in data
        assert _reload(default).view_mode == "cover"
        reader.refresh_from_db()
        assert reader.fit_to == "W"


class CatchupShowAndTopTestCase(_CatchupCase):
    """Show and top move together, and alone only where they stay coherent."""

    def test_pair_and_show_alone(self) -> None:
        pair = _browser()
        comics = _browser(top="comics")
        custom = _browser(top="imprints", show={**_FACTORY_SHOW, "imprints": True})
        new_show = {**_FACTORY_SHOW, "publishers": False}
        self._put({"browser": {"topCollection": "series", "showPublishers": False}})
        pair = _reload(pair)
        assert pair.top_collection == "series"
        assert _show(pair) == new_show
        assert _reload(comics).top_collection == "comics"
        assert _show(comics) == new_show
        assert _reload(custom).top_collection == "imprints"
        assert _show(custom) == {**_FACTORY_SHOW, "imprints": True}

    def test_show_remap_skips_a_row_whose_top_it_hides(self) -> None:
        hidden = _browser(top="series")
        moved = _browser(top="comics")
        self._put({"browser": {"showSeries": False}})
        assert _show(hidden) == _FACTORY_SHOW
        assert _reload(hidden).top_collection == "series"
        assert _show(moved) == {**_FACTORY_SHOW, "series": False}

    def test_top_move_skips_a_row_whose_show_hides_it(self) -> None:
        hides = _browser(show={**_FACTORY_SHOW, "series": False})
        reaches = _browser(show={**_FACTORY_SHOW, "imprints": True})
        pair = _browser()
        self._put({"browser": {"topCollection": "series"}})
        assert _reload(hides).top_collection == "publishers"
        assert _reload(reaches).top_collection == "series"
        assert _reload(pair).top_collection == "series"

    def test_last_route_repair(self) -> None:
        empty = _browser()
        zero = _browser(route=("root", (0,), 1))
        paged = _browser(route=("root", (0,), 2))
        elsewhere = _browser(route=("series", (3,), 1))
        stays_top = _browser(top="comics")
        data = self._put({"browser": {"topCollection": "folders"}})
        for row in (_reload(empty), _reload(zero)):
            assert row.top_collection == "folders"
            assert row.last_route.collection == "folders"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        assert _reload(paged).last_route.collection == "root"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        assert _reload(elsewhere).last_route.collection == "series"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        stays_top = _reload(stays_top)
        assert stays_top.top_collection == "comics"
        assert stays_top.last_route.collection == "root"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        assert data["applied"]["lastRoute"] == 2  # noqa: PLR2004

    def test_resolved_old_value_is_matched(self) -> None:
        """A stored folders that fell back to publishers is matched as publishers."""
        row = SettingsDefaults.objects.get(pk=1)
        row.top_collection = "folders"
        row.save()
        from codex.choices.admin import AdminFlagChoices
        from codex.models import AdminFlag

        AdminFlag.objects.filter(key=AdminFlagChoices.FOLDER_VIEW.value).update(
            on=False
        )
        seeded = _browser()
        self._put({"browser": {"topCollection": "series"}})
        assert _reload(seeded).top_collection == "series"


class ReachTestCase(_CatchupCase):
    """Reach counts the rows the catch-up then moves."""

    def test_counts_match_the_catchup(self) -> None:
        _browser()
        _browser(order_by="sort_name")
        _browser(top="folders", order_by="filename")
        _browser(order_by="created_at", bookmark="READ")
        SettingsReader.objects.create(session_id=_session_key(), client="api")
        SettingsReader.objects.create(
            session_id=_session_key(), client="api", fit_to="O"
        )
        response = self.client.get(_REACH_URL)
        assert response.status_code == HTTPStatus.OK, response.content
        reach = response.json()["data"]
        data = self._put(
            {
                "browser": {"orderBy": "size", "bookmark": "UNREAD"},
                "reader": {"fitTo": "H"},
            }
        )
        applied = data["applied"]
        for key in ("orderBy", "bookmark", "fitTo"):
            assert reach[key] == applied[key], key
        assert reach["orderBy"] == 3  # noqa: PLR2004
        assert reach["fitTo"] == 1

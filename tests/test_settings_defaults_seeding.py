"""Admin site default settings seed new rows and resets; OPDS stays factory."""

import json
from http import HTTPStatus
from importlib import import_module
from types import MappingProxyType
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.test import Client, RequestFactory
from rest_framework.request import Request

from codex.models.settings import ClientChoices, SettingsBrowser, SettingsReader
from codex.views.opds.start import OPDSStartViewMixin
from codex.views.reader.params import ReaderParamsView
from codex.views.settings import SettingsBaseView
from tests.settings_defaults_helpers import (
    BROWSER_SETTINGS_URL,
    FOLDER_COLUMNS,
    READER_SETTINGS_URL,
    TEST_PASSWORD,
    SettingsDefaultsCase,
    data_of,
    set_defaults,
)

_ROW_KEYS = (
    "top_collection",
    "order_by",
    "order_reverse",
    "view_mode",
    "twenty_four_hour_time",
    "always_show_filename",
    "table_columns",
)
_FACTORY_ROW = MappingProxyType(
    {
        "top_collection": "publishers",
        "order_by": "",
        "order_reverse": False,
        "view_mode": "cover",
        "twenty_four_hour_time": False,
        "always_show_filename": False,
        "table_columns": {},
        "show": (True, False, True, False),
        "bookmark": "",
        "route": ("root", [], 1),
    }
)


def _flatten(row: SettingsBrowser) -> dict:
    """Flatten a browser row and its related rows for one comparison."""
    show = row.show
    route = row.last_route  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
    return {
        **{key: getattr(row, key) for key in _ROW_KEYS},
        "show": (show.publishers, show.imprints, show.series, show.volumes),
        "bookmark": row.filters.bookmark,  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        "route": (route.collection, route.pks, route.page),
    }


def _session_row(client: Client) -> SettingsBrowser:
    return SettingsBrowser.objects.select_related("show", "filters", "last_route").get(
        session_id=client.session.session_key, client=ClientChoices.API, name=""
    )


class NewSessionSeedingTestCase(SettingsDefaultsCase):
    """A new anonymous row is seeded from the site defaults."""

    @staticmethod
    def _anonymous_row() -> SettingsBrowser:
        client = Client()
        response = client.get(BROWSER_SETTINGS_URL)
        assert response.status_code == HTTPStatus.OK, response.content
        return _session_row(client)

    def test_factory_session_is_unchanged(self) -> None:
        assert _flatten(self._anonymous_row()) == _FACTORY_ROW

    def test_admin_defaults_seed_a_new_session(self) -> None:
        set_defaults(
            top_collection="folders",
            show_imprints=True,
            order_by="created_at",
            order_reverse=True,
            view_mode="table",
            twenty_four_hour_time=True,
            always_show_filename=True,
            bookmark="UNREAD",
            table_columns={"folders": FOLDER_COLUMNS},
        )
        assert _flatten(self._anonymous_row()) == {
            "top_collection": "folders",
            "order_by": "created_at",
            "order_reverse": True,
            "view_mode": "table",
            "twenty_four_hour_time": True,
            "always_show_filename": True,
            # Never seeded: the SPA falls back to the site default per collection.
            "table_columns": {},
            "show": (True, True, True, False),
            "bookmark": "UNREAD",
            "route": ("folders", [], 1),
        }

    def test_arcs_default_seeds_the_arcs_route(self) -> None:
        set_defaults(top_collection="arcs")
        row = self._anonymous_row()
        assert row.top_collection == "arcs"
        assert row.last_route.collection == "arcs"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]

    def test_folders_default_lands_without_a_redirect(self) -> None:
        """The old Default View folders landed on publishers via a 303."""
        set_defaults(top_collection="folders")
        client = Client()
        client.get(BROWSER_SETTINGS_URL)
        row = SettingsBrowser.objects.select_related("last_route").get(
            session_id=client.session.session_key
        )
        assert row.last_route.collection == "folders"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        response = client.get("/api/v4/browse/folders")
        assert response.status_code == HTTPStatus.OK, response.content


class ReaderSeedingTestCase(SettingsDefaultsCase):
    """The global reader row is seeded with the site reader defaults."""

    def test_settings_get_seeds_the_global_row(self) -> None:
        set_defaults(fit_to="H", page_transition=False)
        client = Client()
        response = client.get(f"{READER_SETTINGS_URL}?scopes=global")
        assert response.status_code == HTTPStatus.OK, response.content
        scope = data_of(response)["scopes"]["global"]
        assert scope["fitTo"] == "H"
        assert scope["pageTransition"] is False

    @staticmethod
    def _params_view() -> ReaderParamsView:
        request = RequestFactory().get("/")
        engine = import_module(settings.SESSION_ENGINE)
        request.session = engine.SessionStore()
        request.user = AnonymousUser()
        view = ReaderParamsView()
        view.request = Request(request)
        view.kwargs = {}
        return view

    def test_params_view_first_seeds_the_global_row(self) -> None:
        """The generic create used to store a blank, unseeded row."""
        set_defaults(fit_to="H", reading_direction="rtl")
        view = self._params_view()
        params = view.load_params_from_settings()
        assert params["fit_to"] == "H"
        assert params["reading_direction"] == "rtl"
        row = SettingsReader.objects.get(session_id=view.request.session.session_key)
        assert row.fit_to == "H"

    def test_concurrent_create_does_not_raise(self) -> None:
        """A global row created in the race window is returned, not re-inserted."""
        view = self._params_view()
        session_key = view._ensure_session_key()  # noqa: SLF001
        existing = SettingsReader.objects.create(
            session_id=session_key, client=ClientChoices.API, fit_to="O"
        )
        with patch.object(
            SettingsBaseView, "_get_or_create_settings_session", return_value=None
        ):
            params = view.load_params_from_settings()
        assert params["fit_to"] == "O"
        assert SettingsReader.objects.filter(session_id=session_key).count() == 1
        assert SettingsReader.objects.get(session_id=session_key).pk == existing.pk


class ResetTestCase(SettingsDefaultsCase):
    """Browser and reader resets write the site defaults."""

    def test_browser_reset_writes_the_site_defaults(self) -> None:
        set_defaults(
            top_collection="folders",
            view_mode="table",
            bookmark="READ",
            table_columns={"folders": FOLDER_COLUMNS},
        )
        client = Client()
        client.patch(
            BROWSER_SETTINGS_URL,
            data=json.dumps(
                {
                    "viewMode": "cover",
                    "tableColumns": {"comics": ["cover", "name"]},
                    "filters": {"bookmark": "UNREAD"},
                }
            ),
            content_type="application/json",
        )
        response = client.delete(BROWSER_SETTINGS_URL)
        assert response.status_code == HTTPStatus.OK, response.content
        data = data_of(response)
        wire = (data["topCollection"], data["viewMode"], data["filters"]["bookmark"])
        assert wire == ("folders", "table", "READ")
        assert data["tableColumns"] == {}
        assert _flatten(_session_row(client)) == {
            **_FACTORY_ROW,
            "top_collection": "folders",
            "view_mode": "table",
            "bookmark": "READ",
            # An emptied route stores the reset's no-pks as [0].
            "route": ("folders", [0], 1),
        }

    def test_reader_reset_writes_the_site_defaults(self) -> None:
        client = Client()
        client.get(f"{READER_SETTINGS_URL}?scopes=global")
        set_defaults(fit_to="S", cache_book=True)
        response = client.delete(
            READER_SETTINGS_URL,
            data=json.dumps({"scope": "global"}),
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.OK, response.content
        row = SettingsReader.objects.get(session_id=client.session.session_key)
        assert row.fit_to == "S"
        assert row.cache_book is True


class OPDSTestCase(SettingsDefaultsCase):
    """OPDS keeps the factory defaults, except a new row's top collection."""

    def test_start_page_params_are_factory(self) -> None:
        view = type("StartView", (OPDSStartViewMixin, SettingsBaseView), {})()
        before = view.init_params()
        set_defaults(
            top_collection="series",
            show_publishers=False,
            order_by="created_at",
            view_mode="table",
            bookmark="UNREAD",
        )
        after = view.init_params()
        assert after == before == SettingsBaseView.get_browser_factory_params()
        assert after["top_collection"] == "publishers"
        assert after["order_by"] == ""
        assert after["filters"]["bookmark"] == ""

    def test_new_opds_row_gets_the_top_collection_only(self) -> None:
        user = User.objects.create_user(username="opds", password=TEST_PASSWORD)
        set_defaults(
            top_collection="series",
            order_by="created_at",
            view_mode="table",
            bookmark="UNREAD",
        )
        row = SettingsBaseView._create_browser_settings(  # noqa: SLF001
            user, None, ClientChoices.OPDS, {"name": ""}
        )
        assert row.top_collection == "series"
        assert row.order_by == ""
        assert row.view_mode == "cover"
        assert row.filters.bookmark == ""  # pyright: ignore[reportAttributeAccessIssue]
        assert row.last_route.collection == "root"  # pyright: ignore[reportAttributeAccessIssue]

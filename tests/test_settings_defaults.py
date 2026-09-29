"""Admin site default settings: storage, factory parity and the admin API."""

from http import HTTPStatus
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.choices.browser import (
    BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS,
    BROWSER_ORDER_BY_CHOICES,
    SETTINGS_DEFAULTS_ORDER_BY_CHOICES,
)
from codex.choices.reader import READER_DEFAULTS
from codex.librarian.notifier.tasks import ADMIN_FLAGS_CHANGED_TASK
from codex.models import SettingsDefaults
from codex.models.settings import (
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserShow,
)
from codex.settings.db import get_browser_defaults, get_reader_defaults
from tests.settings_defaults_helpers import (
    FOLDER_COLUMNS,
    QUEUE,
    REACH_URL,
    SHOW_KEYS,
    TEST_PASSWORD,
    URL,
    SettingsDefaultsCase,
    data_of,
    put,
    set_defaults,
    set_flag,
)


def _field_default(model, name: str):
    return model._meta.get_field(name).get_default()


def _factory_wire() -> dict:
    """Spell out the factory values on the wire, independently of the model."""
    return {
        "browser": {
            "topCollection": "publishers",
            "showPublishers": True,
            "showImprints": False,
            "showSeries": True,
            "showVolumes": False,
            "orderBy": "",
            "orderReverse": False,
            "viewMode": "cover",
            "twentyFourHourTime": False,
            "alwaysShowFilename": False,
            "bookmark": "",
            "tableColumns": {},
        },
        "reader": {
            "fitTo": "W",
            "readingDirection": "ltr",
            "twoPages": False,
            "pageTransition": True,
            "cacheBook": False,
        },
    }


class FactoryParityTestCase(SettingsDefaultsCase):
    """The singleton's factory values are today's defaults."""

    def test_browser_field_defaults_match_the_settings_models(self) -> None:
        for key in (
            "top_collection",
            "order_by",
            "order_reverse",
            "view_mode",
            "twenty_four_hour_time",
            "always_show_filename",
            "table_columns",
        ):
            assert _field_default(SettingsDefaults, key) == _field_default(
                SettingsBrowser, key
            ), key
        for key in SHOW_KEYS:
            assert _field_default(SettingsDefaults, f"show_{key}") == _field_default(
                SettingsBrowserShow, key
            ), key
        assert _field_default(SettingsDefaults, "bookmark") == _field_default(
            SettingsBrowserFilters, "bookmark"
        )
        assert _field_default(SettingsDefaults, "table_columns") == {}

    def test_reader_field_defaults_match_reader_defaults(self) -> None:
        for key in (
            "fit_to",
            "reading_direction",
            "two_pages",
            "page_transition",
            "cache_book",
        ):
            assert _field_default(SettingsDefaults, key) == READER_DEFAULTS[key], key

    def test_fresh_get_equals_factory(self) -> None:
        response = self.client.get(URL)
        assert response.status_code == HTTPStatus.OK, response.content
        data = data_of(response)
        expected = _factory_wire()
        assert data["factory"] == expected
        assert {"browser": data["browser"], "reader": data["reader"]} == expected

    def test_put_response_carries_factory(self) -> None:
        response = put(self.client, {"browser": {"viewMode": "table"}})
        assert response.status_code == HTTPStatus.OK, response.content
        data = data_of(response)
        assert data["browser"]["viewMode"] == "table"
        assert data["factory"] == _factory_wire()

    def test_resolver_without_a_row_is_factory(self) -> None:
        SettingsDefaults.objects.all().delete()
        assert get_browser_defaults() == {
            "top_collection": "publishers",
            "order_by": "",
            "order_reverse": False,
            "view_mode": "cover",
            "twenty_four_hour_time": False,
            "always_show_filename": False,
            "bookmark": "",
            "table_columns": {},
            "show": {
                "publishers": True,
                "imprints": False,
                "series": True,
                "volumes": False,
            },
        }
        assert get_reader_defaults() == dict(READER_DEFAULTS)

    def test_resolver_falls_back_for_out_of_choice_values(self) -> None:
        """Vocabulary drift in a stored value never reaches a settings row."""
        SettingsDefaults.objects.filter(pk=1).update(
            order_by="gone", bookmark="GONE", fit_to="Z", table_columns={"x": ["y"]}
        )
        browser = get_browser_defaults()
        assert browser["order_by"] == ""
        assert browser["bookmark"] == ""
        assert browser["table_columns"] == {}
        assert get_reader_defaults()["fit_to"] == "W"

    def test_resolver_top_collection_follows_folder_view(self) -> None:
        set_defaults(top_collection="folders")
        assert get_browser_defaults()["top_collection"] == "folders"
        set_flag(AdminFlagChoices.FOLDER_VIEW, on=False)
        assert get_browser_defaults()["top_collection"] == "publishers"


class OrderByChoicesTestCase(TestCase):
    """The admin order_by vocabulary is the automatic sort plus standing sorts."""

    def test_excluded_keys_are_the_unsupported_extra_sorts(self) -> None:
        excluded = set(BROWSER_ORDER_BY_CHOICES) - set(
            SETTINGS_DEFAULTS_ORDER_BY_CHOICES
        )
        assert excluded == BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS
        assert "" in SETTINGS_DEFAULTS_ORDER_BY_CHOICES


class PutValidationTestCase(SettingsDefaultsCase):
    """Strict validation: an incoherent default is a 400 and nothing is stored."""

    def _assert_rejected(self, payload: dict) -> None:
        before = SettingsDefaults.objects.get(pk=1).updated_at
        response = put(self.client, payload)
        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert SettingsDefaults.objects.get(pk=1).updated_at == before

    def test_top_collection_hidden_by_show(self) -> None:
        self._assert_rejected({"browser": {"topCollection": "imprints"}})

    def test_folders_with_folder_view_off(self) -> None:
        set_flag(AdminFlagChoices.FOLDER_VIEW, on=False)
        self._assert_rejected({"browser": {"topCollection": "folders"}})

    def test_folders_with_folder_view_on(self) -> None:
        response = put(self.client, {"browser": {"topCollection": "folders"}})
        assert response.status_code == HTTPStatus.OK, response.content

    def test_unsupported_order_by(self) -> None:
        for order_by in sorted(BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS):
            self._assert_rejected({"browser": {"orderBy": order_by}})

    def test_two_pages_with_a_vertical_direction(self) -> None:
        self._assert_rejected({"reader": {"twoPages": True, "readingDirection": "ttb"}})

    def test_unknown_bookmark(self) -> None:
        self._assert_rejected({"browser": {"bookmark": "SOMETIMES"}})

    def test_unknown_table_column(self) -> None:
        self._assert_rejected({"browser": {"tableColumns": {"folders": ["nope"]}}})

    def test_unknown_table_collection(self) -> None:
        self._assert_rejected({"browser": {"tableColumns": {"x": ["cover"]}}})

    def test_empty_table_column_list(self) -> None:
        self._assert_rejected({"browser": {"tableColumns": {"folders": []}}})

    def test_partial_put_checks_the_merged_instance(self) -> None:
        """Hiding the stored top collection is as incoherent as picking it hidden."""
        set_defaults(top_collection="imprints", show_imprints=True)
        self._assert_rejected({"browser": {"showImprints": False}})
        set_defaults(two_pages=True)
        self._assert_rejected({"reader": {"readingDirection": "btt"}})

    def test_errors_are_a_flat_field_map(self) -> None:
        response = put(self.client, {"browser": {"bookmark": "SOMETIMES"}})
        detail = response.json()["errors"][0]["detail"]
        assert "bookmark" in detail

    def test_valid_put_saves(self) -> None:
        response = put(
            self.client,
            {
                "browser": {
                    "bookmark": "UNREAD",
                    "tableColumns": {"folders": FOLDER_COLUMNS},
                },
                "reader": {"fitTo": "H"},
            },
        )
        assert response.status_code == HTTPStatus.OK, response.content
        row = SettingsDefaults.objects.get(pk=1)
        assert row.bookmark == "UNREAD"
        assert row.table_columns == {"folders": FOLDER_COLUMNS}
        assert row.fit_to == "H"
        assert data_of(response)["browser"]["tableColumns"] == {
            "folders": FOLDER_COLUMNS
        }


class PermissionsTestCase(SettingsDefaultsCase):
    """Only staff reach the admin endpoints, Non-Users or not."""

    def _assert_denied(self, client: Client) -> None:
        denied = {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}
        assert client.get(URL).status_code in denied
        assert put(client, {"browser": {"viewMode": "table"}}).status_code in denied
        assert client.get(REACH_URL).status_code in denied
        assert SettingsDefaults.objects.get(pk=1).view_mode == "cover"

    def test_anonymous_is_denied(self) -> None:
        for on in (False, True):
            set_flag(AdminFlagChoices.NON_USERS, on=on)
            self._assert_denied(Client())

    def test_non_staff_is_denied(self) -> None:
        user = User.objects.create_user(username="reader", password=TEST_PASSWORD)
        client = Client()
        client.force_login(user)
        self._assert_denied(client)

    def test_staff_reach(self) -> None:
        response = self.client.get(REACH_URL)
        assert response.status_code == HTTPStatus.OK, response.content
        assert "orderBy" in data_of(response)


class BroadcastTestCase(SettingsDefaultsCase):
    """A PUT tells every client to refetch /session, after the commit."""

    def test_put_enqueues_after_commit(self) -> None:
        with patch(QUEUE) as queue:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
                response = put(self.client, {"browser": {"viewMode": "table"}})
            assert response.status_code == HTTPStatus.OK, response.content
            queue.put.assert_not_called()
            for callback in callbacks:
                callback()
        queue.put.assert_called_once_with(ADMIN_FLAGS_CHANGED_TASK)

    def test_rejected_put_does_not_enqueue(self) -> None:
        with (
            patch(QUEUE) as queue,
            self.captureOnCommitCallbacks(execute=True),  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        ):
            response = put(self.client, {"browser": {"bookmark": "SOMETIMES"}})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        queue.put.assert_not_called()

"""Tests for the per-top-collection sort memory (issue #415)."""

import json
from typing import Any, Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models.settings import SettingsBrowser
from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.startup import init_admin_flags
from codex.views.browser.settings import apply_collection_order_memory

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_CREATED: Final = 201
_HTTP_BAD_REQUEST: Final = 400
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
_FOLDERS_SETTINGS_URL: Final = "/api/v4/browse/folders/settings"
_SAVED_URL: Final = "/api/v4/browse/publishers/saved-settings"

_ADDED_TIME_DESC: Final = {
    "orderBy": "created_at",
    "orderReverse": True,
    "orderExtraKeys": [],
}


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class CollectionOrderMemoryModelTestCase(TestCase):
    """The field is wired into the generic settings machinery."""

    def test_default_is_empty_dict(self):
        field = SettingsBrowser._meta.get_field("collection_order_memory")
        assert field.default is dict
        assert field.default() == {}

    def test_direct_keys_includes_field(self):
        # DIRECT_KEYS membership is what carries the field through load,
        # save, reset and saved-view cloning.
        assert "collection_order_memory" in SettingsBrowser.DIRECT_KEYS


class CollectionOrderMemorySerializerTestCase(TestCase):
    """The validator cleans leniently instead of rejecting."""

    @staticmethod
    def _validated(memory):
        serializer = BrowserSettingsSerializer(data={"collectionOrderMemory": memory})
        assert serializer.is_valid(), serializer.errors
        return serializer.validated_data["collection_order_memory"]

    def test_valid_memory_round_trips_as_snake_case(self):
        cleaned = self._validated(
            {"comics": {**_ADDED_TIME_DESC, "orderExtraKeys": [{"key": "year"}]}}
        )
        assert cleaned == {
            "comics": {
                "order_by": "created_at",
                "order_reverse": True,
                "order_extra_keys": [{"key": "year", "reverse": False}],
            }
        }

    def test_unknown_top_collection_dropped(self):
        cleaned = self._validated(
            {"nope": _ADDED_TIME_DESC, "comics": _ADDED_TIME_DESC}
        )
        assert set(cleaned) == {"comics"}

    def test_unknown_order_by_dropped(self):
        assert self._validated({"comics": {"orderBy": "not_a_sort"}}) == {}

    def test_search_score_never_remembered(self):
        # Relevance ordering only means anything while its search runs.
        assert self._validated({"comics": {"orderBy": "search_score"}}) == {}

    def test_extra_keys_cleaned_without_raising(self):
        cleaned = self._validated(
            {
                "comics": {
                    "orderBy": "sort_name",
                    "orderExtraKeys": [
                        "garbage",
                        {"key": "story_arc_number"},
                        {"key": "year", "reverse": True},
                        {"key": "year"},
                    ],
                }
            }
        )
        # Unsortable-as-an-extra and duplicate entries go; the first
        # ``year`` survives with its own reverse flag.
        assert cleaned["comics"]["order_extra_keys"] == [
            {"key": "year", "reverse": True}
        ]

    def test_non_dict_order_is_rejected(self):
        # Type garbage still 400s at the field layer, like table_columns.
        serializer = BrowserSettingsSerializer(
            data={"collectionOrderMemory": {"comics": 5}}
        )
        assert not serializer.is_valid()


class CollectionOrderMemoryHelperTestCase(TestCase):
    """The server-side stash/restore used when the server moves the top."""

    @staticmethod
    def _params(**overrides) -> dict[str, Any]:
        params: dict[str, Any] = {
            "top_collection": "publishers",
            "order_by": "sort_name",
            "order_reverse": False,
            "order_extra_keys": [],
            "collection_order_memory": {},
            "search": "",
        }
        params.update(overrides)
        return params

    def test_stashes_the_departing_sort(self):
        params = self._params(order_by="created_at", order_reverse=True)
        apply_collection_order_memory(params, "publishers", "folders")
        assert params["collection_order_memory"]["publishers"] == {
            "order_by": "created_at",
            "order_reverse": True,
            "order_extra_keys": [],
        }

    def test_restores_the_arriving_sort(self):
        params = self._params(
            collection_order_memory={
                "folders": {
                    "order_by": "filename",
                    "order_reverse": True,
                    "order_extra_keys": [],
                }
            }
        )
        apply_collection_order_memory(params, "publishers", "folders")
        assert params["order_by"] == "filename"
        assert params["order_reverse"] is True

    def test_unremembered_collection_keeps_the_current_sort(self):
        params = self._params(order_by="created_at")
        apply_collection_order_memory(params, "publishers", "comics")
        assert params["order_by"] == "created_at"

    def test_no_change_is_a_noop(self):
        params = self._params()
        apply_collection_order_memory(params, "publishers", "publishers")
        assert params["collection_order_memory"] == {}

    def test_active_search_keeps_its_sort(self):
        params = self._params(
            order_by="search_score",
            search="batman",
            collection_order_memory={
                "folders": {
                    "order_by": "filename",
                    "order_reverse": False,
                    "order_extra_keys": [],
                }
            },
        )
        apply_collection_order_memory(params, "publishers", "folders")
        assert params["order_by"] == "search_score"
        # ...and relevance ordering is not filed against publishers.
        assert "publishers" not in params["collection_order_memory"]

    def test_unset_sort_is_not_remembered(self):
        params = self._params(order_by="")
        apply_collection_order_memory(params, "publishers", "folders")
        assert params["collection_order_memory"] == {}


class CollectionOrderMemoryRoundTripTestCase(TestCase):
    """End-to-end through the settings HTTP endpoint."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="order_memory_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _patch(self, payload: dict):
        return self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _get(self, url: str = _SETTINGS_URL) -> dict:
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def test_default_get_is_empty(self):
        assert self._get()["collectionOrderMemory"] == {}

    def test_patch_persists_to_the_row(self):
        memory = {"comics": _ADDED_TIME_DESC}
        response = self._patch({"collectionOrderMemory": memory})
        assert response.status_code == _HTTP_OK, response.content
        assert self._get()["collectionOrderMemory"] == memory
        row = SettingsBrowser.objects.get(user=self.user, name="")
        assert row.collection_order_memory == {
            "comics": {
                "order_by": "created_at",
                "order_reverse": True,
                "order_extra_keys": [],
            }
        }

    def test_patch_drops_unknown_top_collection(self):
        response = self._patch(
            {"collectionOrderMemory": {"nope": _ADDED_TIME_DESC}},
        )
        assert response.status_code == _HTTP_OK, response.content
        assert self._get()["collectionOrderMemory"] == {}

    def test_settings_get_accepts_a_memory_query_string(self):
        """A URL-encoded JSON map in the query string must not 400."""
        memory = {"comics": _ADDED_TIME_DESC}
        url = f"{_SETTINGS_URL}?collectionOrderMemory={json.dumps(memory)}"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

    def test_browse_page_query_string_persists_the_memory(self):
        """
        The browse page is what actually stores an echoed memory map.

        The browser sends its whole settings object as query params on
        every page fetch, and that request persists them; the store
        never PATCHes the map on its own.
        """
        memory = {"comics": _ADDED_TIME_DESC}
        url = f"/api/v4/browse/publishers?page=1&collectionOrderMemory={json.dumps(memory)}"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        row = SettingsBrowser.objects.get(user=self.user, name="")
        assert row.collection_order_memory == {
            "comics": {
                "order_by": "created_at",
                "order_reverse": True,
                "order_extra_keys": [],
            }
        }

    def test_delete_resets_the_memory(self):
        self._patch({"collectionOrderMemory": {"comics": _ADDED_TIME_DESC}})
        response = self.client.delete(_SETTINGS_URL)
        assert response.status_code == _HTTP_OK, response.content
        assert self._get()["collectionOrderMemory"] == {}

    def test_saved_view_round_trips_the_memory(self):
        memory = {"comics": _ADDED_TIME_DESC}
        assert self._patch({"collectionOrderMemory": memory}).status_code == _HTTP_OK

        save_resp = self.client.post(
            _SAVED_URL,
            data=json.dumps({"name": "AddedTime"}),
            content_type="application/json",
        )
        assert save_resp.status_code == _HTTP_CREATED, save_resp.content
        listed = next(
            entry
            for entry in _v4(self.client.get(_SAVED_URL))["savedSettings"]
            if entry["name"] == "AddedTime"
        )

        # Reset so the loaded values can only come from the saved row.
        self.client.delete(_SETTINGS_URL)
        load_resp = self.client.get(f"{_SAVED_URL}/{listed['pk']}")
        assert load_resp.status_code == _HTTP_OK, load_resp.content
        assert _v4(load_resp)["settings"]["collectionOrderMemory"] == memory

    def test_url_forced_top_collection_swaps_the_sort(self):
        """
        A url that forces a different top collection swaps sorts too.

        Entering the folders url while the stored top collection is
        publishers is a collection switch the browser store never sees, so
        the settings GET has to file the publisher sort and hand back the
        folder one itself.
        """
        folder_order = {
            "orderBy": "filename",
            "orderReverse": True,
            "orderExtraKeys": [],
        }
        assert (
            self._patch(
                {
                    "orderBy": "created_at",
                    "orderReverse": True,
                    "collectionOrderMemory": {"folders": folder_order},
                }
            ).status_code
            == _HTTP_OK
        )

        # The client names the collection in the path and the query, and
        # the settings GET reads the query one when it validates the top.
        body = self._get(f"{_FOLDERS_SETTINGS_URL}?collection=folders")

        assert body["topCollection"] == "folders"
        assert body["orderBy"] == "filename"
        assert body["orderReverse"] is True
        # The sort publishers was left in is filed on the way past.
        assert body["collectionOrderMemory"]["publishers"] == {
            "orderBy": "created_at",
            "orderReverse": True,
            "orderExtraKeys": [],
        }

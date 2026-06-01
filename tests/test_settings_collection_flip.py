"""
Phase 2 value-flip: the collection vocabulary round-trips end to end.

After the ``Group`` enum + DB migration flip, browser settings speak the
collection vocabulary on the wire AND in storage (``"publishers"``, no char
dialect, no dummy ``0`` root). These pin the API PATCH→GET round-trip and the
underlying row values — proving the value-flip + the 0044 migration.
"""

import json
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models.settings import SettingsBrowser
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.flip")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"


def _v4(response):
    body = response.json()
    return body["data"] if isinstance(body, dict) and "data" in body else body


class SettingsCollectionFlipTestCase(TestCase):
    """Char wire ↔ collection storage for browser settings."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.user = User.objects.create_user(username="flip", password=_TEST_PASSWORD)
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _browser_row(self) -> SettingsBrowser:
        return SettingsBrowser.objects.select_related("show", "last_route").get(
            user=self.user
        )

    def test_show_collection_wire_stores_collection_columns(self) -> None:
        """PATCH collection ``show`` → collection GET; DB row holds the flags."""
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(
                {
                    "show": {
                        "publishers": True,
                        "imprints": True,
                        "series": False,
                        "volumes": False,
                    }
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        show = _v4(self.client.get(_SETTINGS_URL))["show"]
        assert show == {
            "publishers": True,
            "imprints": True,
            "series": False,
            "volumes": False,
        }
        row = self._browser_row().show
        assert row.publishers is True
        assert row.imprints is True
        assert row.series is False
        assert row.volumes is False

    def test_top_group_collection_wire_stores_collection(self) -> None:
        """PATCH ``topGroup="series"`` → same GET; DB stores ``"series"``."""
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"topGroup": "series"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        assert _v4(self.client.get(_SETTINGS_URL))["topGroup"] == "series"
        assert self._browser_row().top_group == "series"

    def test_defaults_store_collection_and_no_root_zero(self) -> None:
        """A fresh row defaults to collection values on the migrated schema."""
        # Touch settings so the row + its related rows are created.
        assert self.client.get(_SETTINGS_URL).status_code == _HTTP_OK
        row = self._browser_row()
        last_route = row.last_route  # ty: ignore[unresolved-attribute]
        # Model defaults are now collection values.
        assert row.top_group == "publishers"
        assert last_route.collection == "root"
        # The dummy 0 root sentinel is gone from stored pks.
        assert 0 not in (last_route.pks or [])

"""
Stats API keys: per-admin keys for ``/api/v4/admin/stats``.

What these tests pin:

* A stats key logs in by ``?apiKey=`` and by ``Authorization: Bearer``, as
  the admin who owns it, and records its use.
* It stops working when its owner is demoted or deactivated.
* A device key does not open the Stats API; neither does a universal key
  passed as ``?apiKey=``.
* A session admin still gets the stats without any key, and still does
  with the Stats API Keys flag off, which refuses every key.
* The payload no longer carries a key.
"""

from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.choices.api_key import UNIVERSAL_KEY_NAME, ApiKeyScope
from codex.models import AdminFlag
from codex.models.api_key import UserApiKey
from codex.startup import init_admin_flags

_URL: Final = "/api/v4/admin/stats"
_PASSWORD: Final = "stats-key-test-pw"  # noqa: S105
_HTTP_OK: Final = 200
_REFUSED: Final = frozenset({401, 403})
_STATS: Final = {"config": {"library_count": 1}}


class StatsApiKeyTestCase(TestCase):
    """The Stats view's key login."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", email="", password=_PASSWORD
        )
        self.api_key, self.key = UserApiKey.create_for_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            self.admin, "Grafana", ApiKeyScope.STATS
        )
        # The stats are counted on another thread, which the test
        # transaction locks out; only the credential is under test.
        patcher = patch("codex.views.admin.stats.CodexStats")
        stats = patcher.start()
        stats.return_value.get.return_value = _STATS
        self.addCleanup(patcher.stop)

    @staticmethod
    def _get(query: str = "", auth: str = ""):
        return Client().get(f"{_URL}{query}", HTTP_AUTHORIZATION=auth)

    def test_query_param(self) -> None:
        assert self._get(f"?apiKey={self.key}").status_code == _HTTP_OK

    def test_bearer(self) -> None:
        assert self._get(auth=f"Bearer {self.key}").status_code == _HTTP_OK

    def test_no_key_is_refused(self) -> None:
        assert self._get().status_code in _REFUSED
        assert self._get("?apiKey=nope").status_code in _REFUSED

    def test_use_is_recorded(self) -> None:
        self._get(f"?apiKey={self.key}")
        self.api_key.refresh_from_db()
        assert self.api_key.last_used_at is not None

    def test_a_demoted_or_inactive_owner_is_refused(self) -> None:
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        assert self._get(f"?apiKey={self.key}").status_code in _REFUSED
        User.objects.filter(pk=self.admin.pk).update(is_staff=True, is_active=False)
        assert self._get(f"?apiKey={self.key}").status_code in _REFUSED
        assert self._get(auth=f"Bearer {self.key}").status_code in _REFUSED

    def test_other_scopes_are_refused(self) -> None:
        _, device_key = UserApiKey.create_for_user(self.admin, "Kobo")
        universal_secret = "a-migrated-bearer-token"  # noqa: S105
        UserApiKey.adopt(
            self.admin, UNIVERSAL_KEY_NAME, ApiKeyScope.UNIVERSAL, universal_secret
        )
        assert self._get(f"?apiKey={device_key}").status_code in _REFUSED
        assert self._get(auth=f"Bearer {device_key}").status_code in _REFUSED
        assert self._get(f"?apiKey={universal_secret}").status_code in _REFUSED

    def test_a_session_admin_needs_no_key(self) -> None:
        client = Client()
        client.force_login(self.admin)
        assert client.get(_URL).status_code == _HTTP_OK

    def test_the_flag_off_refuses_keys_but_not_the_session(self) -> None:
        AdminFlag.objects.filter(key=AdminFlagChoices.STATS_API.value).update(on=False)
        assert self._get(f"?apiKey={self.key}").status_code in _REFUSED
        assert self._get(auth=f"Bearer {self.key}").status_code in _REFUSED
        client = Client()
        client.force_login(self.admin)
        assert client.get(_URL).status_code == _HTTP_OK
        AdminFlag.objects.filter(key=AdminFlagChoices.STATS_API.value).update(on=True)
        assert self._get(f"?apiKey={self.key}").status_code == _HTTP_OK

    def test_the_payload_carries_no_key(self) -> None:
        response = self._get(f"?apiKey={self.key}")
        assert response.status_code == _HTTP_OK
        config = response.json()["data"]["config"]
        assert config == {"libraryCount": 1}
        assert self.key not in response.content.decode()

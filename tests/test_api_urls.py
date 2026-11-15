"""
``GET /api/v4/api-urls``: the URLs the API Access dialog shows.

Each API appears only while it is on and only to a visitor who may use it:
OPDS to anyone who may browse (anonymous Non Users visitors included),
KOReader sync to a logged-in user, the Stats API to staff.
"""

from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag
from codex.startup import init_admin_flags

_URL: Final = "/api/v4/api-urls"
_PASSWORD: Final = "api-urls-test-pw"  # noqa: S105
_HTTP_OK: Final = 200
_REFUSED: Final = frozenset({401, 403})
_OPDS: Final = {"opdsV1": "/opds/v1.2/", "opdsV2": "/opds/v2.0/"}
_KOREADER: Final = {"koreader": "/koreader"}
_STATS: Final = {"stats": "/api/v4/admin/stats"}


def _set_flag(key: AdminFlagChoices, *, on: bool) -> None:
    AdminFlag.objects.filter(key=key.value).update(on=on)


class ApiUrlsTestCase(TestCase):
    """Which URLs each visitor gets."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _set_flag(AdminFlagChoices.NON_USERS, on=True)
        _set_flag(AdminFlagChoices.KOREADER_SYNC, on=True)
        self.user = User.objects.create_user(username="reader", password=_PASSWORD)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", email="", password=_PASSWORD
        )

    @staticmethod
    def _urls(user=None) -> dict:
        client = Client()
        if user:
            client.force_login(user)
        response = client.get(_URL)
        assert response.status_code == _HTTP_OK, response.status_code
        return response.json()["data"]

    def test_anonymous_gets_opds_only(self) -> None:
        assert self._urls() == _OPDS

    def test_anonymous_is_refused_without_non_users(self) -> None:
        _set_flag(AdminFlagChoices.NON_USERS, on=False)
        assert Client().get(_URL).status_code in _REFUSED

    def test_a_user_gets_koreader_too(self) -> None:
        assert self._urls(self.user) == {**_OPDS, **_KOREADER}

    def test_staff_get_stats_too(self) -> None:
        assert self._urls(self.admin) == {**_OPDS, **_KOREADER, **_STATS}

    def test_an_api_that_is_off_is_absent(self) -> None:
        _set_flag(AdminFlagChoices.KOREADER_SYNC, on=False)
        assert self._urls(self.admin) == {**_OPDS, **_STATS}
        _set_flag(AdminFlagChoices.STATS_API, on=False)
        assert self._urls(self.admin) == _OPDS
        _set_flag(AdminFlagChoices.OPDS, on=False)
        assert self._urls(self.admin) == {}

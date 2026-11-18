"""
KOReader and API key logins at the edges.

* KOReader sends ``x-auth-user`` as UTF-8 bytes and ASGI decodes every
  header as latin-1, so a non-ASCII username never matched.
* A path under ``koreader/`` that no route matches fell through to the
  web UI's catch-all: a redirect to an HTML page, which a device reads as
  a successful login.
* README promises every failed login reaches the failed-login log; wrong
  KOReader, Bearer and Stats keys did not.
"""

from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.failed_login_log import failed_login_filter
from codex.models.api_key import UserApiKey
from tests.api_key_fixtures import (
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    KOSYNC_ACCEPT,
    KOSYNC_AUTH,
    REFUSED,
    ApiKeyFixture,
    md5,
    set_flag,
)
from tests.reader_fixtures import PASSWORD

_NON_ASCII_NAME: Final = "Ñandú"
_WRONG_MD5: Final = "0" * 32
_STATS_URL: Final = "/api/v4/admin/stats"


def _as_asgi_header(value: str) -> str:
    """Return what ASGI hands Django for a header sent as UTF-8 bytes."""
    return value.encode().decode("latin-1")


class KOSyncEdgeTestCase(ApiKeyFixture):
    """The kosync auth header and the routes under ``koreader/``."""

    @override
    def setUp(self) -> None:
        super().setUp()
        set_flag(AdminFlagChoices.KOREADER_SYNC, on=True)

    def test_a_non_ascii_username_logs_in(self) -> None:
        user = User.objects.create_user(username=_NON_ASCII_NAME, password=PASSWORD)
        _, key = UserApiKey.create_for_user(user, "Kobo")
        response = Client().get(
            KOSYNC_AUTH,
            HTTP_ACCEPT=KOSYNC_ACCEPT,
            HTTP_X_AUTH_USER=_as_asgi_header(_NON_ASCII_NAME),
            HTTP_X_AUTH_KEY=md5(key),
        )
        assert response.status_code == HTTP_OK, response.content

    def test_an_unknown_path_under_koreader_is_a_json_404(self) -> None:
        for path in ("/koreader/nothing", "/koreader//users/auth", "/koreader/"):
            response = Client().get(
                path,
                HTTP_ACCEPT=KOSYNC_ACCEPT,
                HTTP_X_AUTH_USER=self.user.username,
                HTTP_X_AUTH_KEY=md5(self.key),
            )
            assert response.status_code == HTTP_NOT_FOUND, (path, response)
            assert response["Content-Type"].startswith("application/"), path
            assert "json" in response["Content-Type"], path


class _CaptureSink:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, message) -> None:
        self.lines.append(str(message))


class FailedKeyLoginLogTestCase(ApiKeyFixture):
    """Every refused key reaches the failed-login log."""

    @override
    def setUp(self) -> None:
        super().setUp()
        set_flag(AdminFlagChoices.KOREADER_SYNC, on=True)
        set_flag(AdminFlagChoices.STATS_API, on=True)
        self.sink = _CaptureSink()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.sink_id = logger.add(  # pyright: ignore[reportUninitializedInstanceVariable]
            self.sink, level="WARNING", format="{message}", filter=failed_login_filter
        )

    @override
    def tearDown(self) -> None:
        logger.remove(self.sink_id)
        super().tearDown()

    def _lines(self) -> list[str]:
        logger.complete()
        return [line for line in self.sink.lines if "Failed login" in line]

    def test_a_wrong_kosync_key_is_logged(self) -> None:
        response = Client().get(
            KOSYNC_AUTH,
            HTTP_ACCEPT=KOSYNC_ACCEPT,
            HTTP_X_AUTH_USER=self.user.username,
            HTTP_X_AUTH_KEY=_WRONG_MD5,
            REMOTE_ADDR="198.51.100.7",
        )
        assert response.status_code == HTTP_UNAUTHORIZED
        lines = self._lines()
        assert len(lines) == 1, lines
        assert "198.51.100.7" in lines[0]
        assert f"user={self.user.username}" in lines[0]

    def test_a_wrong_bearer_key_is_logged(self) -> None:
        response = Client().get(
            "/api/v4/auth/keys",
            HTTP_AUTHORIZATION="Bearer " + "a" * 20,
            REMOTE_ADDR="198.51.100.8",
        )
        assert response.status_code in REFUSED
        lines = self._lines()
        assert len(lines) == 1, lines
        assert "198.51.100.8" in lines[0]

    def test_a_wrong_stats_key_is_logged(self) -> None:
        Client().get(f"{_STATS_URL}?apiKey={'b' * 20}", REMOTE_ADDR="198.51.100.9")
        lines = self._lines()
        assert len(lines) == 1, lines
        assert "198.51.100.9" in lines[0]

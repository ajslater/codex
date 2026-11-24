"""What the Add Lists preview says about private and credentialed sources."""

import json
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import Client

from tests.test_reading_list_fetch import _FakeSession
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_PREVIEW: Final = "/api/v4/admin/reading-lists/preview"
_SESSION: Final = "codex.views.admin.reading_lists.imports.reading_list_session"


def _cards(response) -> list[dict]:
    body = response.json()
    return body.get("data", body)["cards"]


class _CountingSession(_FakeSession):
    fetched: list[str] = []  # noqa: RUF012

    @override
    def fetch_url(self, url: str):
        self.fetched.append(url)
        return super().fetch_url(url)


class PreviewSourceTests(ReadingListFixture):
    """A private Metron list previews private; a URL with a password is refused."""

    @override
    def setUp(self) -> None:
        super().setUp()
        caches["tagging"].clear()
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _preview(self, sources: list[dict]):
        _CountingSession.fetched = []
        with patch(_SESSION, _CountingSession):
            response = self.client.post(
                _PREVIEW,
                data=json.dumps({"sources": sources}),
                content_type="application/json",
            )
        assert response.status_code == _OK, response.content
        return _cards(response)

    def test_a_private_metron_list_previews_private(self) -> None:
        """Metron's own private flag carries into the preview card."""
        (card,) = self._preview(
            [{"kind": "metron_list", "ref": "5", "name": "Mine", "private": True}]
        )
        assert card["private"] is True

    def test_a_public_metron_list_previews_public(self) -> None:
        """A list Metron shows everyone is not made private."""
        (card,) = self._preview([{"kind": "metron_list", "ref": "6", "name": "Ours"}])
        assert card["private"] is False

    def test_a_url_with_a_password_is_refused(self) -> None:
        """Codex stores a source's URL, so it never fetches one with a login."""
        url = "https://reader:secret@example.invalid/cw.cbl"
        (card,) = self._preview([{"kind": "url", "ref": url}])
        assert "password" in card["error"]
        assert "secret" not in json.dumps(card)
        assert _CountingSession.fetched == []

    def test_a_plain_url_is_fetched(self) -> None:
        """A URL without a login previews as before."""
        url = "https://example.invalid/cw.cbl"
        (card,) = self._preview([{"kind": "url", "ref": url}])
        assert card["count"] == 4  # noqa: PLR2004
        assert _CountingSession.fetched == [url]

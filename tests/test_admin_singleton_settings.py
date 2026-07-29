"""Smoke tests for /api/v4/admin singleton settings (envelope, PUT updates)."""

import json
from http import HTTPStatus
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

_TEST_PASSWORD: Final = "test-pw-hush-Q807"  # noqa: S105
_EMAIL_PORT: Final = 587
_USER_THROTTLE: Final = 120


def _put_envelope(client, url, payload):
    return client.put(url, data=json.dumps(payload), content_type="application/json")


def _ensure_admin_flags() -> None:
    """Seed AdminFlag + Timestamp rows that startup normally creates."""
    from codex.startup import init_admin_flags, init_timestamps

    init_admin_flags()
    init_timestamps()


class AdminSingletonSettingsTestCase(TestCase):
    """Verify GET/PUT round-trip on the three admin singleton settings views."""

    @override
    def setUp(self) -> None:
        _ensure_admin_flags()
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="adminss", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_email_settings_put(self) -> None:
        """PUT /admin/email-settings returns 200 with the saved row."""
        resp = _put_envelope(
            self.client,
            "/api/v4/admin/email-settings",
            {
                "host": "smtp.example.com",
                "port": _EMAIL_PORT,
                "useTls": True,
                "useSsl": False,
                "timeout": 30,
                "user": "codex",
                "fromAddress": "codex@example.com",
                "subjectPrefix": "[Codex] ",
            },
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        body = resp.json()["data"]
        assert body["host"] == "smtp.example.com"
        assert body["port"] == _EMAIL_PORT

    def test_tagging_defaults_put(self) -> None:
        """PUT /admin/tagging-defaults returns 200 with the saved row."""
        resp = _put_envelope(
            self.client,
            "/api/v4/admin/tagging-defaults",
            {
                "defaultFormats": ["METRON_INFO"],
                "deleteOriginal": False,
                "defaultMatchMode": "auto",
                "defaultPromptsMode": "ask",
                "defaultSources": [],
            },
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        body = resp.json()["data"]
        assert body["defaultFormats"] == ["METRON_INFO"]

    def test_tagging_defaults_preserves_source_order(self) -> None:
        """DefaultSources order (run priority) round-trips comicvine-first."""
        resp = _put_envelope(
            self.client,
            "/api/v4/admin/tagging-defaults",
            {
                "defaultFormats": ["COMIC_INFO"],
                "deleteOriginal": False,
                "defaultMatchMode": "auto",
                "defaultPromptsMode": "ask",
                "defaultSources": ["comicvine", "metron"],
            },
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json()["data"]["defaultSources"] == ["comicvine", "metron"]

    def test_metron_key_retires_a_legacy_login(self) -> None:
        """Saving an API key drops the username & password it replaces."""
        from codex.models import ComicboxTaggingDefaults

        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            metron_user="stored_user",
            metron_password="stored_pw",  # noqa: S106
        )
        resp = _put_envelope(
            self.client, "/api/v4/admin/tagging-defaults", {"metronKey": "token"}
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        body = resp.json()["data"]
        assert body["metronKeySet"] is True
        assert body["hasMetronCredentials"] is True
        # Write-only: the key itself never comes back out.
        assert "metronKey" not in body
        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        assert defaults.metron_key == "token"
        assert defaults.metron_user == ""
        assert defaults.metron_password == ""

    def test_clearing_the_metron_key_clears_a_legacy_login_too(self) -> None:
        from codex.models import ComicboxTaggingDefaults

        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            metron_key="token",
            metron_user="stored_user",
            metron_password="stored_pw",  # noqa: S106
        )
        resp = _put_envelope(
            self.client,
            "/api/v4/admin/tagging-defaults",
            {"metronKey": "", "metronUrl": ""},
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert resp.json()["data"]["hasMetronCredentials"] is False
        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        assert defaults.metron_key == ""
        assert defaults.metron_user == ""
        assert defaults.metron_password == ""

    def test_legacy_login_survives_a_put_that_omits_the_key(self) -> None:
        """A URL-only save, or any other settings save, keeps a stored login."""
        from codex.models import ComicboxTaggingDefaults

        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            metron_user="stored_user",
            metron_password="stored_pw",  # noqa: S106
        )
        resp = _put_envelope(
            self.client,
            "/api/v4/admin/tagging-defaults",
            {"metronUrl": "https://metron.example.com"},
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        body = resp.json()["data"]
        assert body["metronKeySet"] is False
        # A pre-API-key install still reads as configured.
        assert body["hasMetronCredentials"] is True
        defaults = ComicboxTaggingDefaults.objects.get(pk=1)
        assert defaults.metron_user == "stored_user"
        assert defaults.metron_password == "stored_pw"  # noqa: S105

    def test_tagging_defaults_rejects_unknown_source(self) -> None:
        """An unknown source name is a 400, not a silently-stored junk value."""
        resp = _put_envelope(
            self.client,
            "/api/v4/admin/tagging-defaults",
            {
                "defaultFormats": ["COMIC_INFO"],
                "deleteOriginal": False,
                "defaultMatchMode": "auto",
                "defaultPromptsMode": "ask",
                "defaultSources": ["comicvine", "grand_comics_db"],
            },
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.content

    def test_throttle_settings_put(self) -> None:
        """PUT /admin/throttle-settings returns 200 with the saved row."""
        resp = _put_envelope(
            self.client,
            "/api/v4/admin/throttle-settings",
            {
                "anon": 30,
                "user": _USER_THROTTLE,
                "opds": 60,
                "opensearch": 60,
                "resetPassword": 5,
            },
        )
        assert resp.status_code == HTTPStatus.OK, resp.content
        body = resp.json()["data"]
        assert body["user"] == _USER_THROTTLE

"""Integration tests for the /admin/tagging-defaults/validate endpoint."""

from __future__ import annotations

from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.librarian.onlinetag.credential_validator import ValidationResult
from codex.models import ComicboxTaggingDefaults

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_URL: Final = "/api/v3/admin/tagging-defaults/validate"
_HTTP_OK: Final = 200
_HTTP_FORBIDDEN: Final = 403


def _make_admin() -> User:
    return User.objects.create_user(
        username="tagging_validate_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


class TaggingValidateAuthTestCase(TestCase):
    """Endpoint must require admin auth."""

    def test_anonymous_blocked(self) -> None:
        client = Client()
        response = client.post(_URL, data={}, content_type="application/json")
        assert response.status_code == _HTTP_FORBIDDEN

    def test_non_admin_blocked(self) -> None:
        User.objects.create_user(username="regular", password=_TEST_PASSWORD)
        client = Client()
        client.login(username="regular", password=_TEST_PASSWORD)
        response = client.post(_URL, data={}, content_type="application/json")
        assert response.status_code == _HTTP_FORBIDDEN


class TaggingValidateMergeTestCase(TestCase):
    """Form-supplied fields override stored credentials; missing fields fall back."""

    @override
    def setUp(self) -> None:
        self.admin = _make_admin()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.admin)
        ComicboxTaggingDefaults.objects.filter(pk=1).update(
            metron_user="stored_user",
            metron_password="stored_pw",  # noqa: S106
            comicvine_key="stored_key",
        )

    def test_uses_form_overrides_when_provided(self) -> None:
        with patch("codex.views.admin.tagging_validate.validate_credentials") as mocked:
            mocked.return_value = {"metron": ValidationResult(ok=True)}
            response = self.client.post(
                _URL,
                data={
                    "source": "metron",
                    "metron_user": "form_user",
                    "metron_password": "form_pw",
                },
                content_type="application/json",
            )
        assert response.status_code == _HTTP_OK
        creds = mocked.call_args.args[0]
        assert creds.metron_user == "form_user"
        assert creds.metron_password == "form_pw"  # noqa: S105
        assert mocked.call_args.args[1] == {"metron"}

    def test_falls_back_to_stored_when_form_blank(self) -> None:
        with patch("codex.views.admin.tagging_validate.validate_credentials") as mocked:
            mocked.return_value = {"metron": ValidationResult(ok=True)}
            response = self.client.post(
                _URL,
                data={"source": "metron"},
                content_type="application/json",
            )
        assert response.status_code == _HTTP_OK
        creds = mocked.call_args.args[0]
        assert creds.metron_user == "stored_user"
        assert creds.metron_password == "stored_pw"  # noqa: S105

    def test_omitted_source_validates_all_known_sources(self) -> None:
        with patch("codex.views.admin.tagging_validate.validate_credentials") as mocked:
            mocked.return_value = {
                "metron": ValidationResult(ok=True),
                "comicvine": ValidationResult(ok=False, error="bad key"),
            }
            response = self.client.post(_URL, data={}, content_type="application/json")
        assert response.status_code == _HTTP_OK
        assert mocked.call_args.args[1] == frozenset({"metron", "comicvine"})

    def test_response_shape(self) -> None:
        with patch("codex.views.admin.tagging_validate.validate_credentials") as mocked:
            mocked.return_value = {
                "metron": ValidationResult(ok=True),
                "comicvine": ValidationResult(ok=False, error="bad key"),
            }
            response = self.client.post(_URL, data={}, content_type="application/json")
        assert response.status_code == _HTTP_OK
        body = response.json()
        assert body == {
            "results": {
                "metron": {"ok": True, "error": None},
                "comicvine": {"ok": False, "error": "bad key"},
            }
        }

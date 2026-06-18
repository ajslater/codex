"""Unit tests for the online-source credential validator."""

from __future__ import annotations

from typing import Final
from unittest.mock import MagicMock, patch

from comicbox.online_session import OnlineCredentials

from codex.librarian.onlinetag.credential_validator import (
    KNOWN_SOURCES,
    ValidationResult,
    validate_credentials,
)


def _full_creds() -> OnlineCredentials:
    return OnlineCredentials(
        metron_user="user",
        metron_password="pw",  # noqa: S106
        metron_url="",
        comicvine_key="key",
        comicvine_url="",
    )


class TestValidateCredentials:
    """Cover success, auth-error, transport-error, and missing-creds paths."""

    def test_known_sources_set(self) -> None:
        assert frozenset({"metron", "comicvine"}) == KNOWN_SOURCES

    def test_metron_success(self) -> None:
        with patch("mokkari.session.Session") as mocked:
            instance = MagicMock()
            instance.publishers_list.return_value = []
            mocked.return_value = instance
            results = validate_credentials(_full_creds(), {"metron"})
        assert results == {"metron": ValidationResult(ok=True)}
        instance.publishers_list.assert_called_once_with({"page": 1})

    def test_metron_auth_failure(self) -> None:
        from mokkari.exceptions import AuthenticationError

        with patch("mokkari.session.Session") as mocked:
            instance = MagicMock()
            instance.publishers_list.side_effect = AuthenticationError()
            mocked.return_value = instance
            results = validate_credentials(_full_creds(), {"metron"})
        assert results["metron"].ok is False
        assert "authoriz" in (results["metron"].error or "").lower()

    def test_metron_api_error(self) -> None:
        from mokkari.exceptions import ApiError

        with patch("mokkari.session.Session") as mocked:
            instance = MagicMock()
            instance.publishers_list.side_effect = ApiError("boom")
            mocked.return_value = instance
            results = validate_credentials(_full_creds(), {"metron"})
        assert results["metron"] == ValidationResult(ok=False, error="boom")

    def test_metron_missing_creds(self) -> None:
        creds = OnlineCredentials(metron_user="", metron_password="")
        results = validate_credentials(creds, {"metron"})
        assert results["metron"].ok is False
        assert "required" in (results["metron"].error or "").lower()

    def test_comicvine_success(self) -> None:
        with patch("simyan.comicvine.Comicvine") as mocked:
            instance = MagicMock()
            instance.list_publishers.return_value = []
            mocked.return_value = instance
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results == {"comicvine": ValidationResult(ok=True)}
        instance.list_publishers.assert_called_once_with(
            params={"limit": "1"}, max_results=1
        )

    def test_comicvine_auth_failure(self) -> None:
        from simyan.errors import AuthenticationError

        with patch("simyan.comicvine.Comicvine") as mocked:
            instance = MagicMock()
            instance.list_publishers.side_effect = AuthenticationError("bad key")
            mocked.return_value = instance
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results["comicvine"] == ValidationResult(ok=False, error="bad key")

    def test_comicvine_service_error(self) -> None:
        from simyan.errors import ServiceError

        with patch("simyan.comicvine.Comicvine") as mocked:
            instance = MagicMock()
            instance.list_publishers.side_effect = ServiceError("upstream down")
            mocked.return_value = instance
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results["comicvine"] == ValidationResult(ok=False, error="upstream down")

    def test_comicvine_missing_creds(self) -> None:
        creds = OnlineCredentials(comicvine_key="")
        results = validate_credentials(creds, {"comicvine"})
        assert results["comicvine"].ok is False
        assert "required" in (results["comicvine"].error or "").lower()

    def test_default_targets_all_known_sources(self) -> None:
        with (
            patch("mokkari.session.Session") as metron_mock,
            patch("simyan.comicvine.Comicvine") as cv_mock,
        ):
            metron_mock.return_value.publishers_list.return_value = []
            cv_mock.return_value.list_publishers.return_value = []
            results = validate_credentials(_full_creds())
        assert set(results) == KNOWN_SOURCES
        assert all(r.ok for r in results.values())

    def test_unknown_source_silently_skipped(self) -> None:
        results = validate_credentials(_full_creds(), {"bogus"})
        assert results == {}


# Sanity: catch accidental drift between the field set the view forwards
# and the dataclass on the comicbox side.
_EXPECTED_CRED_FIELDS: Final = frozenset(
    {
        "metron_user",
        "metron_password",
        "metron_url",
        "comicvine_key",
        "comicvine_url",
    }
)


def test_online_credentials_fields_stable() -> None:
    """OnlineCredentials field names match what the view forwards into it."""
    assert frozenset(OnlineCredentials.__dataclass_fields__) == _EXPECTED_CRED_FIELDS

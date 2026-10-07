"""Unit tests for the online-source credential validator."""

from dataclasses import replace
from pathlib import Path
from typing import Any, Final
from unittest.mock import MagicMock, patch

from comicbox.config.online.settings import OnlineSourceCredentials
from comicbox.formats.comicvine_api.online_source import ComicVineOnlineSource
from comicbox.formats.metron_api.online_source import MetronOnlineSource
from comicbox.online_session import OnlineCredentials

from codex.librarian.onlinetag.credential_validator import (
    KNOWN_SOURCES,
    RateLimitInfo,
    RateLimitWindowInfo,
    ValidationResult,
    validate_credentials,
)
from codex.settings import COMICBOX_ONLINE_CONFIG

# What Metron's probe returns off the validation response's X-RateLimit-*
# headers. The reset epochs are what codex deliberately drops.
_METRON_WINDOWS: Final = {
    "burst": {"limit": 20, "remaining": 19, "reset_epoch": None},
    "daily": {"limit": 25_000, "remaining": 24_987, "reset_epoch": 1_784_419_200.0},
}
# A response that carried no X-RateLimit-* headers at all.
_EMPTY_METRON_WINDOWS: Final = {
    "burst": {"limit": None, "remaining": None, "reset_epoch": None},
    "daily": {"limit": None, "remaining": None, "reset_epoch": None},
}
# Comic Vine's per-endpoint hourly pools; never shown, whatever they hold.
_COMICVINE_WINDOWS: Final = {
    "origins": {"limit": 200, "remaining": 199, "reset_epoch": 1_784_419_200.0},
}


def _full_creds() -> OnlineCredentials:
    return OnlineCredentials(metron_key="token", comicvine_key="key")


def _legacy_creds() -> OnlineCredentials:
    """Build credentials for an install predating Metron's API keys."""
    return OnlineCredentials(
        metron_user="user",
        metron_password="pw",  # noqa: S106
    )


def _probe(source_cls: type, **kwargs: Any):
    """Patch ``source_cls.probe``; autospec so the mock is called with ``self``."""
    return patch.object(source_cls, "probe", autospec=True, **kwargs)


def _probed_source(probe: MagicMock) -> Any:
    """Return the source instance the (autospecced) probe ran on."""
    probe.assert_called_once()
    return probe.call_args.args[0]


class TestValidateCredentials:
    """Cover success, auth-error, transport-error, and missing-creds paths."""

    def test_known_sources_set(self) -> None:
        assert frozenset({"metron", "comicvine"}) == KNOWN_SOURCES

    def test_metron_success(self) -> None:
        with _probe(MetronOnlineSource, return_value=_EMPTY_METRON_WINDOWS) as probe:
            results = validate_credentials(_full_creds(), {"metron"})
        assert results == {"metron": ValidationResult(ok=True)}
        source = _probed_source(probe)
        assert source._credentials == OnlineSourceCredentials(key="token")  # noqa: SLF001

    def test_metron_success_without_windows(self) -> None:
        """A source that keeps no windows returns None; that is still a pass."""
        with _probe(MetronOnlineSource, return_value=None):
            results = validate_credentials(_full_creds(), {"metron"})
        assert results == {"metron": ValidationResult(ok=True)}

    def test_metron_success_reports_rate_limits(self) -> None:
        """The validation response's live account limits ride along, sans reset."""
        with _probe(MetronOnlineSource, return_value=_METRON_WINDOWS):
            results = validate_credentials(_full_creds(), {"metron"})
        assert results == {
            "metron": ValidationResult(
                ok=True,
                rate_limits=RateLimitInfo(
                    burst=RateLimitWindowInfo(limit=20, remaining=19),
                    sustained=RateLimitWindowInfo(limit=25_000, remaining=24_987),
                ),
            )
        }

    def test_metron_partial_windows_keep_what_was_reported(self) -> None:
        windows = {"daily": {"limit": 5_000, "remaining": None, "reset_epoch": None}}
        with _probe(MetronOnlineSource, return_value=windows):
            results = validate_credentials(_full_creds(), {"metron"})
        assert results["metron"].rate_limits == RateLimitInfo(
            sustained=RateLimitWindowInfo(limit=5_000)
        )

    def test_metron_legacy_login_still_validates(self) -> None:
        """A stored username & password authenticates when no API key is set."""
        with _probe(MetronOnlineSource, return_value=_EMPTY_METRON_WINDOWS) as probe:
            results = validate_credentials(_legacy_creds(), {"metron"})
        assert results == {"metron": ValidationResult(ok=True)}
        # key is None, not "" — mokkari sends a Bearer header for any non-None
        # token, which would shut off the username & password fallback.
        assert _probed_source(probe)._credentials == OnlineSourceCredentials(  # noqa: SLF001
            user="user",
            password="pw",  # noqa: S106
        )

    def test_metron_key_wins_over_legacy_login(self) -> None:
        """Both stored: the token reaches mokkari, which prefers it."""
        creds = OnlineCredentials(
            metron_key="token",
            metron_user="user",
            metron_password="pw",  # noqa: S106
        )
        with _probe(MetronOnlineSource, return_value=_EMPTY_METRON_WINDOWS) as probe:
            results = validate_credentials(creds, {"metron"})
        assert results["metron"].ok is True
        assert _probed_source(probe)._credentials == OnlineSourceCredentials(  # noqa: SLF001
            key="token",
            user="user",
            password="pw",  # noqa: S106
        )

    def test_metron_auth_failure(self) -> None:
        from mokkari.exceptions import AuthenticationError

        with _probe(MetronOnlineSource, side_effect=AuthenticationError()):
            results = validate_credentials(_full_creds(), {"metron"})
        assert results["metron"].ok is False
        assert "authoriz" in (results["metron"].error or "").lower()

    def test_metron_api_error(self) -> None:
        from mokkari.exceptions import ApiError

        with _probe(MetronOnlineSource, side_effect=ApiError("boom")):
            results = validate_credentials(_full_creds(), {"metron"})
        assert results["metron"] == ValidationResult(ok=False, error="boom")

    def test_error_text_is_the_exceptions_first_line(self) -> None:
        """Some upstream errors carry a whole HTML page; the admin sees one line."""
        from mokkari.exceptions import ApiError

        err = ApiError("502 Bad Gateway\n<html><body>nginx</body></html>")
        with _probe(MetronOnlineSource, side_effect=err):
            results = validate_credentials(_full_creds(), {"metron"})
        assert results["metron"] == ValidationResult(ok=False, error="502 Bad Gateway")

    def test_metron_missing_creds(self) -> None:
        creds = OnlineCredentials(metron_key="", metron_user="", metron_password="")
        with _probe(MetronOnlineSource) as probe:
            results = validate_credentials(creds, {"metron"})
        assert results["metron"].ok is False
        assert "api key required" in (results["metron"].error or "").lower()
        probe.assert_not_called()

    def test_metron_half_a_legacy_login_is_not_enough(self) -> None:
        creds = OnlineCredentials(metron_user="user", metron_password="")
        with _probe(MetronOnlineSource) as probe:
            results = validate_credentials(creds, {"metron"})
        assert results["metron"].ok is False
        assert "api key required" in (results["metron"].error or "").lower()
        probe.assert_not_called()

    def test_comicvine_success(self) -> None:
        with _probe(ComicVineOnlineSource, return_value=_COMICVINE_WINDOWS) as probe:
            results = validate_credentials(_full_creds(), {"comicvine"})
        # Comic Vine's hourly pools never become the per-minute/per-day chip.
        assert results == {"comicvine": ValidationResult(ok=True)}
        source = _probed_source(probe)
        # No override means simyan's own default endpoint.
        assert source._credentials == OnlineSourceCredentials(key="key")  # noqa: SLF001
        # Codex's own online settings, so the probe is counted against the
        # same shared rate-limit bucket tagging runs draw on.
        assert source._settings is COMICBOX_ONLINE_CONFIG.online  # noqa: SLF001

    def test_comicvine_custom_url_overrides_the_endpoint(self) -> None:
        """A saved custom URL reaches the source as its base url."""
        creds = OnlineCredentials(
            comicvine_key="key", comicvine_url="https://cv.example.com/api"
        )
        with _probe(ComicVineOnlineSource, return_value=_COMICVINE_WINDOWS) as probe:
            results = validate_credentials(creds, {"comicvine"})
        assert results == {"comicvine": ValidationResult(ok=True)}
        assert _probed_source(probe)._credentials == OnlineSourceCredentials(  # noqa: SLF001
            key="key", url="https://cv.example.com/api"
        )

    def test_comicvine_url_alone_is_not_credentials(self) -> None:
        """A custom URL cannot authenticate; the key is still required."""
        creds = OnlineCredentials(comicvine_url="https://cv.example.com/api")
        with _probe(ComicVineOnlineSource) as probe:
            results = validate_credentials(creds, {"comicvine"})
        assert results["comicvine"].ok is False
        assert "required" in (results["comicvine"].error or "").lower()
        probe.assert_not_called()

    def test_comicvine_auth_failure(self) -> None:
        from simyan.errors import AuthenticationError

        with _probe(ComicVineOnlineSource, side_effect=AuthenticationError("bad key")):
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results["comicvine"] == ValidationResult(ok=False, error="bad key")

    def test_comicvine_rejected_key_fails_through_the_real_simyan(
        self, tmp_path: Path
    ) -> None:
        """
        A bad key must fail validation, not pass it.

        Comic Vine answers a rejected key with HTTP 200 and status_code
        100 in the body. simyan 3.x returned that body verbatim, so the
        listing came back empty and the key validated as good. simyan 4
        maps the status code to an exception, so this patches the HTTP
        session rather than the client, and lets comicbox's real probe
        and simyan's own code decide. The cache dir is pointed at a
        scratch path so the probe's bucket and cache files stay out of
        the developer's config dir.
        """
        online = COMICBOX_ONLINE_CONFIG.online
        config = replace(
            COMICBOX_ONLINE_CONFIG,
            online=replace(online, cache=replace(online.cache, dir=tmp_path)),
        )
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status_code": 100,
            "error": "Invalid API Key",
            "results": [],
        }
        with (
            patch(
                "codex.librarian.onlinetag.credential_validator.COMICBOX_ONLINE_CONFIG",
                config,
            ),
            patch("simyan.comicvine.CachedLimiterSession.request") as request,
        ):
            request.return_value = response
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results == {
            "comicvine": ValidationResult(ok=False, error="Invalid API Key")
        }
        # The probe spent one request, on the origins pool tagging never uses.
        request.assert_called_once()
        assert "/origins" in request.call_args.kwargs["url"]

    def test_comicvine_rate_limit_exhausted(self) -> None:
        """The probe refuses to block on a spent pool; the admin learns why."""
        from simyan.errors import RateLimitError

        err = RateLimitError("the hourly origins budget is spent")
        with _probe(ComicVineOnlineSource, side_effect=err):
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results["comicvine"] == ValidationResult(
            ok=False, error="the hourly origins budget is spent"
        )

    def test_messageless_rate_limit_error_names_its_category(self) -> None:
        """A 429 with no error body is ``RateLimitError(None)``, not "None"."""
        from simyan.errors import RateLimitError

        with _probe(ComicVineOnlineSource, side_effect=RateLimitError(None)):
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results["comicvine"] == ValidationResult(ok=False, error="Rate limited.")

    def test_comicvine_service_error(self) -> None:
        from simyan.errors import ServiceError

        with _probe(ComicVineOnlineSource, side_effect=ServiceError("upstream down")):
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results["comicvine"] == ValidationResult(ok=False, error="upstream down")

    def test_unclassified_messageless_error_names_its_type(self) -> None:
        with _probe(ComicVineOnlineSource, side_effect=ConnectionResetError()):
            results = validate_credentials(_full_creds(), {"comicvine"})
        assert results["comicvine"] == ValidationResult(
            ok=False, error="ConnectionResetError"
        )

    def test_comicvine_missing_creds(self) -> None:
        creds = OnlineCredentials(comicvine_key="")
        results = validate_credentials(creds, {"comicvine"})
        assert results["comicvine"].ok is False
        assert "required" in (results["comicvine"].error or "").lower()

    def test_default_targets_all_known_sources(self) -> None:
        with (
            _probe(MetronOnlineSource, return_value=_EMPTY_METRON_WINDOWS),
            _probe(ComicVineOnlineSource, return_value=_COMICVINE_WINDOWS),
        ):
            results = validate_credentials(_full_creds())
        assert set(results) == KNOWN_SOURCES
        assert all(r.ok for r in results.values())

    def test_unknown_source_silently_skipped(self) -> None:
        results = validate_credentials(_full_creds(), {"bogus"})
        assert results == {}


# Sanity: catch accidental drift in the comicbox dataclass. Codex forwards
# every field here except ``metron_url``, which mokkari ignores entirely.
_EXPECTED_CRED_FIELDS: Final = frozenset(
    {
        "metron_key",
        "metron_user",
        "metron_password",
        "metron_url",
        "comicvine_key",
        "comicvine_url",
    }
)


def test_online_credentials_fields_stable() -> None:
    """OnlineCredentials field names match what comicbox defines."""
    assert frozenset(OnlineCredentials.__dataclass_fields__) == _EXPECTED_CRED_FIELDS

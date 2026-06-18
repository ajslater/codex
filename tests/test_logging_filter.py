"""Tests for the noisy-Forbidden log filter and the credential scrubber."""

import logging
from typing import Final, override

from django.test import TestCase

from codex.settings.logging import (
    DowngradeNoisyForbiddenFilter,
    scrub_secrets,
    scrub_secrets_filter,
)

_FILTER_NAME: Final = "test"


def _build_record(level: int, msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="django.request",
        level=level,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )


class DowngradeNoisyForbiddenFilterTests(TestCase):
    """Cover the level-downgrade logic on the request logger filter."""

    @override
    def setUp(self) -> None:
        """Build one filter shared across the cases."""
        self.flt = DowngradeNoisyForbiddenFilter(_FILTER_NAME)  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_downgrades_noisy_path(self) -> None:
        """First-load profile probe becomes DEBUG."""
        record = _build_record(
            logging.WARNING, "%s: %s", "Forbidden", "/api/v4/auth/profile"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.DEBUG
        assert record.levelname == "DEBUG"

    def test_keeps_unrelated_forbidden_at_warning(self) -> None:
        """A Forbidden on a non-noisy path stays at WARNING."""
        record = _build_record(
            logging.WARNING, "%s: %s", "Forbidden", "/api/v4/admin/users"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.WARNING

    def test_keeps_non_forbidden_at_warning(self) -> None:
        """A Bad Request line through django.request stays at WARNING."""
        record = _build_record(
            logging.WARNING, "%s: %s", "Bad Request", "/api/v4/auth/profile"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.WARNING

    def test_ignores_non_warning_levels(self) -> None:
        """ERROR-level records pass through untouched."""
        record = _build_record(
            logging.ERROR, "%s: %s", "Forbidden", "/api/v4/auth/profile"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.ERROR


class ScrubSecretsTests(TestCase):
    """Cover the credential-scrubbing helper used by LoguruHandler + sinks."""

    def test_redacts_comicvine_api_key(self) -> None:
        """The exact httpx INFO line we saw must lose the api_key value."""
        msg = (
            "HTTP Request: GET https://comicvine.gamespot.com/api/issues/"
            "?api_key=c3f506e4c5406003657c88f4f0d36fb391ef5ae3"
            "&format=json&filter=volume%3A27478%2Cissue_number%3A1"
            '&limit=100&offset=0 "HTTP/1.1 200 OK"'
        )
        scrubbed = scrub_secrets(msg)
        assert "c3f506e4c5406003657c88f4f0d36fb391ef5ae3" not in scrubbed
        assert "api_key=<redacted>" in scrubbed
        # Non-secret params are preserved.
        assert "format=json" in scrubbed
        assert "filter=volume%3A27478%2Cissue_number%3A1" in scrubbed
        assert "offset=0" in scrubbed

    def test_redacts_common_secret_query_params(self) -> None:
        """access_token / token / secret / password / apikey are all masked."""
        cases = (
            ("https://x/?access_token=abc&foo=1", "access_token=<redacted>"),
            ("https://x/?token=abc&foo=1", "token=<redacted>"),
            ("https://x/?secret=abc&foo=1", "secret=<redacted>"),
            ("https://x/?password=abc&foo=1", "password=<redacted>"),
            ("https://x/?apikey=abc&foo=1", "apikey=<redacted>"),
            ("https://x/?api-key=abc&foo=1", "api-key=<redacted>"),
        )
        for url, expected in cases:
            scrubbed = scrub_secrets(url)
            assert "abc" not in scrubbed, f"leaked secret in {url!r}"
            assert expected in scrubbed
            assert "foo=1" in scrubbed

    def test_redacts_authorization_header(self) -> None:
        """Authorization Basic/Bearer values get masked even if logged."""
        basic = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        bearer = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        assert "dXNlcjpwYXNzd29yZA==" not in scrub_secrets(basic)
        assert "Basic <redacted>" in scrub_secrets(basic)
        assert "eyJhbGciOiJIUzI1NiJ9.payload.sig" not in scrub_secrets(bearer)
        assert "Bearer <redacted>" in scrub_secrets(bearer)

    def test_passes_through_unrelated_messages(self) -> None:
        """Messages without credentials must be returned verbatim."""
        msg = "user 42 updated metadata on comic 17"
        assert scrub_secrets(msg) == msg

    def test_filter_mutates_record_message(self) -> None:
        """The loguru sink filter rewrites record['message'] in place."""
        record = {
            "message": "https://x/?api_key=DEADBEEF&format=json",
        }
        assert scrub_secrets_filter(record) is True
        assert "DEADBEEF" not in record["message"]
        assert "api_key=<redacted>" in record["message"]

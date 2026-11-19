"""Tests for the request log filters and the credential scrubber."""

import logging
from http import HTTPStatus
from typing import Final, override

from django.test import RequestFactory, TestCase

from codex.settings.logging import (
    DowngradeNoisyForbiddenFilter,
    DowngradeOPDSAuthChallengeFilter,
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


def _build_response_record(
    status: HTTPStatus, path: str, *, authorization: str = "", script_name: str = ""
) -> logging.LogRecord:
    """Build the record ``django.utils.log.log_response`` emits for a 4xx."""
    headers = {"Authorization": authorization} if authorization else None
    request = RequestFactory(SCRIPT_NAME=script_name).get(path, headers=headers)
    record = _build_record(logging.WARNING, "%s: %s", status.phrase, request.path)
    # Django passes these through ``extra``, which lands in ``__dict__``.
    record.__dict__.update(status_code=status.value, request=request)
    return record


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

    def test_downgrades_noisy_path_under_path_prefix(self) -> None:
        """``server.url_path_prefix`` stays in ``path``, not ``path_info``."""
        record = _build_response_record(
            HTTPStatus.FORBIDDEN, "/api/v4/auth/profile", script_name="/codex"
        )
        assert record.getMessage() == "Forbidden: /codex/api/v4/auth/profile"
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


class DowngradeOPDSAuthChallengeFilterTests(TestCase):
    """An OPDS 401 to a request with no credentials is a routine challenge."""

    @override
    def setUp(self) -> None:
        """Build one filter shared across the cases."""
        self.flt = DowngradeOPDSAuthChallengeFilter(_FILTER_NAME)  # pyright: ignore[reportUninitializedInstanceVariable]

    def _assert_level(self, record: logging.LogRecord, level: int) -> None:
        assert self.flt.filter(record) is True
        assert record.levelno == level
        assert record.levelname == logging.getLevelName(level)

    def test_downgrades_feed_challenge(self) -> None:
        """A feed fetched with no credentials becomes DEBUG."""
        record = _build_response_record(HTTPStatus.UNAUTHORIZED, "/opds/v1.2/folders/3")
        self._assert_level(record, logging.DEBUG)

    def test_downgrades_bin_challenge(self) -> None:
        """A cover fetched with no credentials becomes DEBUG."""
        record = _build_response_record(
            HTTPStatus.UNAUTHORIZED, "/opds/bin/c/17/cover.webp"
        )
        self._assert_level(record, logging.DEBUG)

    def test_keeps_refused_basic_at_warning(self) -> None:
        """A 401 to Basic credentials is a refused login."""
        record = _build_response_record(
            HTTPStatus.UNAUTHORIZED,
            "/opds/v1.2/",
            authorization="Basic dXNlcjpwYXNzd29yZA==",
        )
        self._assert_level(record, logging.WARNING)

    def test_keeps_refused_bearer_at_warning(self) -> None:
        """A 401 to a Bearer key is a refused login."""
        record = _build_response_record(
            HTTPStatus.UNAUTHORIZED, "/opds/v2.0/", authorization="Bearer nope"
        )
        self._assert_level(record, logging.WARNING)

    def test_keeps_api_unauthorized_at_warning(self) -> None:
        """Form logins carry credentials in the body, so only OPDS qualifies."""
        record = _build_response_record(HTTPStatus.UNAUTHORIZED, "/api/v4/auth/login/")
        self._assert_level(record, logging.WARNING)

    def test_ignores_other_statuses(self) -> None:
        """Only 401 is a challenge."""
        for status in (HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND):
            record = _build_response_record(status, "/opds/v1.2/")
            self._assert_level(record, logging.WARNING)

    def test_ignores_record_without_usable_request(self) -> None:
        """No request to inspect means no downgrade."""
        for extra in ({}, {"request": None}, {"request": object()}):
            record = _build_record(
                logging.WARNING, "%s: %s", "Unauthorized", "/opds/v1.2/"
            )
            record.__dict__.update(status_code=HTTPStatus.UNAUTHORIZED.value, **extra)
            self._assert_level(record, logging.WARNING)

    def test_downgrades_under_path_prefix(self) -> None:
        """``server.url_path_prefix`` stays in ``path``, not ``path_info``."""
        record = _build_response_record(
            HTTPStatus.UNAUTHORIZED, "/opds/v1.2/", script_name="/codex"
        )
        assert record.getMessage() == "Unauthorized: /codex/opds/v1.2/"
        self._assert_level(record, logging.DEBUG)


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

"""Tests for the optional failed-login log feature."""

from typing import Final, override
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_login_failed
from django.test import RequestFactory, TestCase
from loguru import logger

from codex.failed_login_log import (
    RequestContextMiddleware,
    _current_request,
    failed_login_filter,
    get_client_ip,
    on_login_failed,
)

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_WRONG_PASSWORD: Final = "wrong-pw-hush-S106"  # noqa: S105


class _CaptureSink:
    """Loguru sink that appends formatted records to a list."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, msg) -> None:
        self.lines.append(str(msg).rstrip("\n"))


class GetClientIpTests(TestCase):
    """Cover the IP-extraction helper."""

    @override
    def setUp(self) -> None:
        """Build a fresh RequestFactory for each test."""
        self.rf = RequestFactory()  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_none_request(self) -> None:
        """Missing request resolves to the missing-value sentinel."""
        assert get_client_ip(None) == "-"

    def test_remote_addr_only(self) -> None:
        """REMOTE_ADDR is returned when no XFF header is present."""
        request = self.rf.get("/", REMOTE_ADDR="10.0.0.5")
        assert get_client_ip(request) == "10.0.0.5"

    def test_forwarded_leftmost(self) -> None:
        """X-Forwarded-For wins, leftmost entry is returned."""
        request = self.rf.get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.5",
            REMOTE_ADDR="10.0.0.5",
        )
        assert get_client_ip(request) == "203.0.113.7"

    def test_forwarded_disabled(self) -> None:
        """Disabling trust falls back to REMOTE_ADDR even when XFF present."""
        request = self.rf.get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
            REMOTE_ADDR="10.0.0.5",
        )
        with patch(
            "codex.failed_login_log.AUTH_FAILED_LOGIN_LOG_TRUST_FORWARDED_FOR",
            new=False,
        ):
            assert get_client_ip(request) == "10.0.0.5"

    def test_empty_forwarded_falls_back(self) -> None:
        """Blank XFF doesn't shadow REMOTE_ADDR."""
        request = self.rf.get("/", HTTP_X_FORWARDED_FOR="   ", REMOTE_ADDR="10.0.0.9")
        assert get_client_ip(request) == "10.0.0.9"


class OnLoginFailedTests(TestCase):
    """Exercise the signal receiver via a captured loguru sink."""

    @override
    def setUp(self) -> None:
        """Attach an in-memory sink and a user for credential tests."""
        self.sink = _CaptureSink()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.sink_id = logger.add(  # pyright: ignore[reportUninitializedInstanceVariable]
            self.sink,
            level="WARNING",
            format="{message}",
            filter=failed_login_filter,
        )
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="alice", password=_TEST_PASSWORD
        )
        user_login_failed.connect(on_login_failed)
        self.rf = RequestFactory()  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        """Tear down the sink and disconnect the signal."""
        user_login_failed.disconnect(on_login_failed)
        logger.remove(self.sink_id)

    def _wait_for_lines(self, count: int = 1) -> None:
        """Drain loguru's enqueue buffer before asserting."""
        logger.complete()
        assert len(self.sink.lines) >= count, self.sink.lines

    def test_receiver_logs_ip_and_username(self) -> None:
        """Direct authenticate() with request propagates the IP into the log."""
        request = self.rf.post("/login/", REMOTE_ADDR="198.51.100.42")
        result = authenticate(
            request=request, username="alice", password=_WRONG_PASSWORD
        )
        assert result is None
        self._wait_for_lines()
        assert "Failed login from 198.51.100.42 user=alice" in self.sink.lines[-1]

    def test_receiver_uses_context_when_request_omitted(self) -> None:
        """Caller-omitted request is recovered from the contextvar."""
        request = self.rf.post("/login/", REMOTE_ADDR="198.51.100.99")
        token = _current_request.set(request)
        try:
            result = authenticate(username="alice", password=_WRONG_PASSWORD)
            assert result is None
        finally:
            _current_request.reset(token)
        self._wait_for_lines()
        assert "198.51.100.99" in self.sink.lines[-1]

    def test_unknown_user_logs_username(self) -> None:
        """Nonexistent username still produces a log line — fail2ban needs it."""
        request = self.rf.post("/login/", REMOTE_ADDR="198.51.100.10")
        authenticate(request=request, username="ghost", password=_WRONG_PASSWORD)
        self._wait_for_lines()
        assert "user=ghost" in self.sink.lines[-1]
        assert "198.51.100.10" in self.sink.lines[-1]


class RequestContextMiddlewareTests(TestCase):
    """Sanity-check the contextvar middleware in isolation."""

    def test_sync_sets_and_resets_contextvar(self) -> None:
        """Sync path sets the contextvar during the call and clears it after."""
        rf = RequestFactory()
        request = rf.get("/x")
        seen = {}

        def _inner(_req):
            seen["during"] = _current_request.get()
            return "response"

        middleware = RequestContextMiddleware(_inner)
        result = middleware(request)
        assert result == "response"
        assert seen["during"] is request
        assert _current_request.get() is None

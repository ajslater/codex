"""Tests for the anonymous stats payload and how it is transmitted."""

import json
from datetime import timedelta
from email.message import Message
from lzma import decompress
from typing import override
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest
from django.http import QueryDict
from django.test import TestCase
from django.utils import timezone

from codex.librarian.telemeter import telemeter
from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import Timestamp
from codex.serializers.admin.stats import (
    AdminStatsRequestSerializer,
    StatsSerializer,
)

EXPECTED_SECTIONS = (
    "platform",
    "config",
    "sessions",
    "collections",
    "file_types",
    "metadata",
    "usage",
    "identifiers",
    "admin_flags",
    "tagging",
    "auth",
    "email",
    "throttle",
    "deployment",
)


class _FakeResponse:
    """Stand in for http.client.HTTPResponse."""

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False


class _DebugOnlyLog:
    """
    A log that can only be called at debug.

    Failing to reach the stats server is never the user's problem, so it is
    reported at debug and nowhere else. Exposing only that method makes a
    revert to warning() an AttributeError rather than a silent regression.
    """

    def __init__(self) -> None:
        self.logged: list[str] = []

    def debug(self, msg) -> None:
        self.logged.append(msg)

    def sent_stats_quietly(self, *fragments: str) -> bool:
        """Whether one debug line reports a failed send, mentioning fragments."""
        return any(
            "Failed to send anonymous stats" in msg
            and all(fragment in msg for fragment in fragments)
            for msg in self.logged
        )


class TelemeterTransportTestCase(TestCase):
    """The url and headers the telemeter actually puts on the wire."""

    @override
    def setUp(self) -> None:
        """
        Seed the admin flags the send path reads.

        Without the SEND_TELEMETRY row, _send_telemetry raises DoesNotExist at
        the flag lookup and never reaches the mocked urlopen, so a transport
        test would pass without exercising any transport.
        """
        from codex.startup import init_admin_flags

        init_admin_flags()

    def test_posts_to_wire_version_two(self) -> None:
        """Codex 2.2.3 and later report the expanded payload as version 2."""
        assert telemeter._VERSION == "2"  # noqa: SLF001
        assert telemeter._POST.endswith("/stats/codex/2")  # noqa: SLF001

    def test_credentials_are_not_in_the_url(self) -> None:
        """
        Userinfo in the url makes http.client read the password as a port.

        That raised InvalidURL on every send, silently, for months.
        """
        netloc = urlsplit(telemeter._POST).netloc  # noqa: SLF001
        assert "@" not in netloc
        assert netloc

    def test_credentials_move_to_an_authorization_header(self) -> None:
        """The credentials taken out of the url are still sent."""
        headers = telemeter._new_headers()  # noqa: SLF001
        assert headers["Content-Type"] == "application/xz"
        assert headers.get("Authorization", "").startswith("Basic ")

    def test_posts_compressed_json(self) -> None:
        """The body is the lzma-compressed payload, and the url is reachable."""
        payload = {"uuid": "abc", "stats": {"platform": {"codex_version": "2.2.3"}}}
        with patch.object(telemeter, "urlopen") as mock_urlopen:
            mock_urlopen.return_value = _FakeResponse()
            telemeter._post_stats(payload)  # noqa: SLF001

        request = mock_urlopen.call_args.args[0]
        assert request.get_method() == "POST"
        assert request.host == urlsplit(telemeter._POST).netloc  # noqa: SLF001
        assert json.loads(decompress(request.data).decode()) == payload

    def test_http_error_reaches_the_caller(self) -> None:
        """A rejected post must not look like a successful one."""
        error = HTTPError(telemeter._POST, 500, "boom", Message(), None)  # noqa: SLF001
        with (
            patch.object(telemeter, "urlopen", side_effect=error),
            pytest.raises(HTTPError),
        ):
            telemeter._post_stats({"uuid": "abc"})  # noqa: SLF001

    def test_a_rejected_post_is_survived_quietly(self) -> None:
        """A stats server that refuses the post must not break or alarm."""
        log = _DebugOnlyLog()
        error = HTTPError(telemeter._POST, 500, "boom", Message(), None)  # noqa: SLF001
        with patch.object(telemeter, "urlopen", side_effect=error):
            telemeter.send_telemetry(log)
        # The status code, not merely some line: the outer handler logs at
        # debug too, so presence alone would pass even if this one regressed
        # to warning and blew up on the log above.
        assert log.sent_stats_quietly("500")

    def test_an_unreachable_server_is_survived_quietly(self) -> None:
        """Nor is a timeout or a dns failure the user's problem."""
        log = _DebugOnlyLog()
        with patch.object(telemeter, "urlopen", side_effect=URLError(TimeoutError())):
            telemeter.send_telemetry(log)
        assert log.sent_stats_quietly("TimeoutError")

    def test_a_failed_send_still_waits_a_week(self) -> None:
        """
        The timestamp marks the attempt, not the success.

        Retrying a failed send would turn a stats outage into a stream of
        requests from every install at once, so the week's slot is spent
        either way.
        """
        ts = telemeter.get_telemeter_timestamp()
        stale = timezone.now() - timedelta(days=30)
        # A queryset update writes the column that auto_now would overwrite.
        Timestamp.objects.filter(pk=ts.pk).update(updated_at=stale)
        error = HTTPError(telemeter._POST, 503, "down", Message(), None)  # noqa: SLF001
        with patch.object(telemeter, "urlopen", side_effect=error):
            telemeter.send_telemetry(_DebugOnlyLog())
        ts.refresh_from_db()
        assert ts.updated_at > stale


class TelemeterStatsTestCase(TestCase):
    """The shape of the payload the telemeter builds."""

    @override
    def setUp(self) -> None:
        from codex.startup import init_admin_flags, init_timestamps

        init_admin_flags()
        init_timestamps()

    def test_every_section_present(self) -> None:
        """A full payload carries every section, in payload order."""
        stats = CodexStats().get()
        assert tuple(stats) == EXPECTED_SECTIONS

    def test_serializer_reports_every_payload_field(self) -> None:
        """
        The admin Stats tab is the visible contract for what is collected.

        Anything the telemeter sends must also be rendered there, or the page
        understates what leaves the install.
        """
        stats = CodexStats().get()
        data = StatsSerializer(stats).data
        assert set(stats) == set(data)
        for section, values in stats.items():
            if not isinstance(values, dict) or not isinstance(data[section], dict):
                continue
            assert not set(values) - set(data[section]), (
                f"{section} fields missing from StatsSerializer"
            )

    def test_params_select_sections(self) -> None:
        """The admin endpoint can ask for a subset."""
        stats = CodexStats({"platform": {}, "throttle": {}}).get()
        assert set(stats) == {"platform", "throttle"}

    def test_default_admin_request_returns_every_section(self) -> None:
        """
        A section missing from the request serializer vanishes from the tab.

        AdminStatsRequestSerializer fills in every declared section, so params
        is always truthy and the section gate drops anything undeclared. Adding
        a section to StatsSerializer without adding it here renders an empty
        table with no error, which is how the identifiers section was lost.
        """
        request_serializer = AdminStatsRequestSerializer(data=QueryDict("ts=1"))
        assert request_serializer.is_valid(), request_serializer.errors
        params = dict(request_serializer.validated_data)
        assert tuple(CodexStats(params).get()) == EXPECTED_SECTIONS

    def test_new_sections_have_content(self) -> None:
        """The seeded singletons and flags produce real values."""
        stats = CodexStats().get()
        assert stats["admin_flags"]["send_telemetry"] in (True, False)
        assert "url_path_prefix_set" in stats["deployment"]
        assert "throttle_anon" in stats["throttle"]
        assert "bookmark_count" in stats["usage"]
        assert "library_read_only_count" in stats["config"]
        assert "multi_sort_count" in stats["sessions"]
        assert "comic_community_rating_count" in stats["metadata"]

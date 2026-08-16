"""
Version comparison and the version payload the browser reads.

``outdated`` used to be computed in javascript, wrongly: the comparison
returned true on the first greater version part without ever stopping on
a lesser one, and it was called with one argument instead of two so it
returned false always. It lives here now, on the side that can read a
PEP 440 version.
"""

from __future__ import annotations

from queue import SimpleQueue
from typing import override
from unittest.mock import patch

import pytest
from django.test import TestCase

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.models.admin import Timestamp
from codex.startup import init_timestamps
from codex.version import is_outdated
from codex.views.version import version_payload


@pytest.mark.parametrize(
    ("installed", "latest", "expected"),
    [
        ("1.0.0", "1.0.1", True),
        ("1.0.0", "2.0.0", True),
        ("1.0.0", "1.0.0", False),
        ("1.0.1", "1.0.0", False),
        # The old javascript read this pair as outdated: 9 > 0 in the
        # third part returned true before the second part could veto.
        ("1.1.0", "1.0.9", False),
        ("1.0.9", "1.1.0", True),
        # A source checkout has no distribution metadata to report.
        ("test", "2.0.0", False),
        ("2.0.0", "not a version", False),
        # Cold cache. Both of these used to raise InvalidVersion.
        ("1.0.0", "", False),
        ("1.0.0", "fetching...", False),
        ("", "1.0.0", False),
        # Never move a stable install onto a prerelease.
        ("1.0.0", "1.1.0a1", False),
        ("1.1.0a1", "1.1.0a2", True),
        ("1.1.0a1", "1.1.0", True),
    ],
)
def test_is_outdated(installed: str, latest: str, *, expected: bool) -> None:
    """The version comparison is total: unparseable means "not outdated"."""
    assert is_outdated(installed, latest) is expected


class VersionPayloadTests(TestCase):
    """The /api/v4/version payload."""

    @override
    def setUp(self) -> None:
        init_timestamps()

    @staticmethod
    def _set_latest(value: str) -> None:
        Timestamp.objects.filter(key=Timestamp.Choices.CODEX_VERSION.value).update(
            value=value
        )

    def test_outdated_when_latest_is_newer(self) -> None:
        self._set_latest("9999.0.0")
        with patch("codex.views.version.VERSION", "1.0.0"):
            payload = version_payload()
        assert payload["latest"] == "9999.0.0"
        assert payload["outdated"] is True

    def test_not_outdated_when_current(self) -> None:
        self._set_latest("1.0.0")
        with patch("codex.views.version.VERSION", "1.0.0"):
            payload = version_payload()
        assert payload["outdated"] is False

    def test_reports_docker(self) -> None:
        """In a container the browser links to the image registry instead."""
        self._set_latest("9999.0.0")
        with (
            patch("codex.views.version.VERSION", "1.0.0"),
            patch("codex.views.version.is_docker", return_value=True),
        ):
            payload = version_payload()
        assert payload["docker"] is True

    def test_cold_cache_is_not_outdated_and_queues_a_fetch(self) -> None:
        """An unfilled cache reports the placeholder, never an update."""
        self._set_latest("")
        queue = SimpleQueue()
        with (
            patch("codex.views.version.VERSION", "1.0.0"),
            patch("codex.views.version.LIBRARIAN_QUEUE", queue),
        ):
            payload = version_payload()
        assert payload["latest"] == "fetching..."
        assert payload["outdated"] is False
        assert isinstance(queue.get_nowait(), CodexLatestVersionTask)

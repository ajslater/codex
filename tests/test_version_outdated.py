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
from typing import Final, override
from unittest.mock import patch

import pytest
from django.test import TestCase

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.models.admin import Timestamp
from codex.startup import init_admin_flags, init_timestamps
from codex.version import is_outdated
from codex.views.version import version_payload

_HTTP_OK: Final = 200
_SESSION_URL: Final = "/api/v4/session"


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
        # Only the deprecated Docker Hub image sets this. The free-text
        # ``warning`` it replaced is gone.
        assert payload["docker_hub"] is False
        assert "warning" not in payload

    def test_reports_docker(self) -> None:
        """In a container the browser links to the image registry instead."""
        self._set_latest("9999.0.0")
        with (
            patch("codex.views.version.VERSION", "1.0.0"),
            patch("codex.views.version.is_docker", return_value=True),
        ):
            payload = version_payload()
        assert payload["docker"] is True

    def test_reports_docker_hub(self) -> None:
        """The deprecated Docker Hub image tells the browser to nag admins."""
        self._set_latest("1.0.0")
        with (
            patch("codex.views.version.VERSION", "1.0.0"),
            patch("codex.views.version.DOCKER_IMAGE_DEPRECATED", new=True),
        ):
            payload = version_payload()
        assert payload["docker_hub"] is True

    def test_session_ships_docker_hub_in_camel_case(self) -> None:
        """The composite session payload carries the flag the snackbar reads."""
        init_admin_flags()
        self._set_latest("1.0.0")
        with patch("codex.views.version.DOCKER_IMAGE_DEPRECATED", new=True):
            response = self.client.get(_SESSION_URL)
        assert response.status_code == _HTTP_OK
        assert response.json()["data"]["version"]["dockerHub"] is True

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

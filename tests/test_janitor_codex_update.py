"""
Codex self-update: gating, installer selection, failure and restart.

The updater used to check the Auto Update admin flag here, which meant
the admin's own Update Codex button did nothing while the flag was off
(and it defaults to off). The flag now gates only the nightly path, in
:mod:`codex.librarian.bookmark.latest_version`.
"""

from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager
from multiprocessing import Event
from threading import Lock
from typing import TYPE_CHECKING, override
from unittest.mock import patch

from django.test import TestCase
from loguru import logger

from codex.librarian.restarter.tasks import CodexRestartTask
from codex.librarian.scribe.janitor.janitor import Janitor
from codex.models.admin import Timestamp
from codex.startup import init_timestamps

if TYPE_CHECKING:
    from collections.abc import Generator

_MODULE = "codex.librarian.scribe.janitor.update"
_INSTALLED = "1.0.0"
# find_spec's return value is only ever truthiness-tested. A uv or
# pipx managed environment really has no pip, so pin the choice
# rather than letting the test read whatever this venv happens to be.
_PIP_FOUND = object()


@contextmanager
def _capture_logs() -> Generator[list[str]]:
    """Collect loguru INFO+ messages emitted inside the ``with`` block."""
    records: list[str] = []
    sink_id = logger.add(records.append, level="INFO", format="{message}")
    try:
        yield records
    finally:
        logger.remove(sink_id)


class _FakeQueue:
    """Record tasks put on the librarian queue without touching multiprocessing."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class CodexUpdateTests(TestCase):
    """Janitor.update_codex."""

    @override
    def setUp(self) -> None:
        init_timestamps()
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.janitor = Janitor(  # pyright: ignore[reportUninitializedInstanceVariable]
            logger, self.queue, Lock(), Event(), online_tag_thread=None
        )

    @staticmethod
    def _set_latest(value: str) -> None:
        Timestamp.objects.filter(key=Timestamp.Choices.CODEX_VERSION.value).update(
            value=value
        )

    @property
    def _restarts(self) -> list:
        return [t for t in self.queue.items if isinstance(t, CodexRestartTask)]

    def test_up_to_date_does_not_install(self) -> None:
        self._set_latest(_INSTALLED)
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.subprocess.run") as run,
        ):
            self.janitor.update_codex(force=False)
        run.assert_not_called()
        assert not self._restarts

    def test_outdated_installs_with_pip(self) -> None:
        """The common case: pip is importable, so upgrade with this python."""
        self._set_latest("2.0.0")
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=_PIP_FOUND),
            patch(f"{_MODULE}.get_version", return_value=_INSTALLED),
            patch(f"{_MODULE}.subprocess.run") as run,
        ):
            self.janitor.update_codex(force=False)
        args, kwargs = run.call_args
        assert args[0] == (sys.executable, "-m", "pip", "install", "--upgrade", "codex")
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        # A hung installer must not wedge the scribe thread forever.
        assert kwargs["timeout"] > 0

    def test_force_installs_when_up_to_date(self) -> None:
        """Forcing ignores the version check and the admin flag alike."""
        self._set_latest(_INSTALLED)
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=_PIP_FOUND),
            patch(f"{_MODULE}.get_version", return_value=_INSTALLED),
            patch(f"{_MODULE}.subprocess.run") as run,
        ):
            self.janitor.update_codex(force=True)
        run.assert_called_once()

    def test_uv_fallback_when_pip_is_missing(self) -> None:
        """Uv and pipx environments have no pip."""
        self._set_latest("2.0.0")
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.get_version", return_value=_INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=None),
            patch(f"{_MODULE}.which", return_value="/opt/bin/uv"),
            patch(f"{_MODULE}.subprocess.run") as run,
        ):
            self.janitor.update_codex(force=False)
        assert run.call_args[0][0] == (
            "/opt/bin/uv",
            "pip",
            "install",
            "--upgrade",
            "--python",
            sys.executable,
            "codex",
        )

    def test_no_installer_logs_an_error(self) -> None:
        """The docker image strips pip. Say so instead of failing silently."""
        self._set_latest("2.0.0")
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=None),
            patch(f"{_MODULE}.which", return_value=None),
            patch(f"{_MODULE}.is_docker", return_value=True),
            patch(f"{_MODULE}.subprocess.run") as run,
            _capture_logs() as logs,
        ):
            self.janitor.update_codex(force=False)
        run.assert_not_called()
        assert any("neither pip nor uv" in line for line in logs)
        assert any("Docker" in line for line in logs)
        assert not self._restarts

    def test_failed_install_does_not_restart(self) -> None:
        """A pip that exits nonzero must not look like a successful update."""
        self._set_latest("2.0.0")
        error = subprocess.CalledProcessError(
            1, "pip", stderr="No matching distribution"
        )
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=_PIP_FOUND),
            patch(f"{_MODULE}.get_version", return_value="2.0.0"),
            patch(f"{_MODULE}.subprocess.run", side_effect=error),
            _capture_logs() as logs,
        ):
            self.janitor.update_codex(force=False)
        assert not self._restarts
        assert any("No matching distribution" in line for line in logs)

    def test_timed_out_install_does_not_restart(self) -> None:
        self._set_latest("2.0.0")
        error = subprocess.TimeoutExpired("pip", 600)
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=_PIP_FOUND),
            patch(f"{_MODULE}.get_version", return_value="2.0.0"),
            patch(f"{_MODULE}.subprocess.run", side_effect=error),
            _capture_logs() as logs,
        ):
            self.janitor.update_codex(force=False)
        assert not self._restarts
        assert any("timed out" in line for line in logs)

    def test_new_version_restarts(self) -> None:
        self._set_latest("2.0.0")
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=_PIP_FOUND),
            patch(f"{_MODULE}.get_version", return_value="2.0.0"),
            patch(f"{_MODULE}.subprocess.run"),
        ):
            self.janitor.update_codex(force=False)
        assert len(self._restarts) == 1

    def test_same_version_does_not_restart(self) -> None:
        """Reinstalling the same version is not a reason to bounce the server."""
        self._set_latest("2.0.0")
        with (
            patch(f"{_MODULE}.VERSION", _INSTALLED),
            patch(f"{_MODULE}.find_spec", return_value=_PIP_FOUND),
            patch(f"{_MODULE}.get_version", return_value=_INSTALLED),
            patch(f"{_MODULE}.subprocess.run"),
        ):
            self.janitor.update_codex(force=False)
        assert not self._restarts

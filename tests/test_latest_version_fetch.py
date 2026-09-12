"""
The PyPI latest-version fetch: caching, backoff and the update chain.

Nothing ever asked for the update half of this before: the nightly
janitor queued a bare version check and no caller passed ``update``, so
the Auto Update admin flag promised a daily update that could not
happen. The nightly task now forces the fetch and asks it to chain.

This daily run is also where the deprecated Docker Hub image nags the
log, so an admin who never opens the web UI still finds out that their
image has stopped being the real one.
"""

from __future__ import annotations

from threading import Lock
from typing import override
from unittest.mock import patch

import pytest
from django.test import TestCase
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.librarian.bookmark.latest_version import (
    CodexLatestVersionUpdater,
    _FetchGate,
)
from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.scribe.janitor.janitor import _NIGHTLY_TASKS
from codex.librarian.scribe.janitor.tasks import JanitorCodexUpdateTask
from codex.models.admin import AdminFlag, Timestamp
from codex.startup import init_admin_flags, init_timestamps
from codex.util import log_docker_hub_deprecation

_MODULE = "codex.librarian.bookmark.latest_version"
_LATEST = "9999.0.0"


class _RecordingLog:
    """Proxy loguru, but keep the warnings where a test can read them."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message) -> None:
        self.warnings.append(str(message))

    def __getattr__(self, name):
        """Everything but ``warning`` behaves like the real logger."""
        return getattr(logger, name)


def test_deprecation_warning_names_the_registry_to_move_to() -> None:
    """A log line nobody can act on is worse than none."""
    log = _RecordingLog()
    with patch("codex.util.DOCKER_IMAGE_DEPRECATED", new=True):
        log_docker_hub_deprecation(log)
    assert len(log.warnings) == 1
    assert "ghcr.io/ajslater/codex" in log.warnings[0]
    assert "migrating-from-docker-hub" in log.warnings[0]


def test_only_the_docker_hub_image_is_nagged() -> None:
    """ghcr.io and native installs must not see a word of this."""
    log = _RecordingLog()
    log_docker_hub_deprecation(log)
    assert not log.warnings


class _FakeQueue:
    """Record tasks put on the librarian queue without touching multiprocessing."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


def test_nightly_version_check_forces_a_fetch_and_may_update() -> None:
    """The only path that can trigger an automatic update."""
    assert CodexLatestVersionTask(force=True, update=True) in _NIGHTLY_TASKS


class LatestVersionFetchTests(TestCase):
    """CodexLatestVersionUpdater.update_latest_version."""

    @override
    def setUp(self) -> None:
        init_timestamps()
        init_admin_flags()
        _FetchGate.next_attempt = 0.0
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.updater = CodexLatestVersionUpdater(logger, self.queue, Lock())  # pyright: ignore[reportUninitializedInstanceVariable, reportArgumentType]  # ty: ignore[invalid-argument-type]

    @override
    def tearDown(self) -> None:
        _FetchGate.next_attempt = 0.0

    @staticmethod
    def _set_auto_update(*, on: bool) -> None:
        AdminFlag.objects.filter(key=AdminFlagChoices.AUTO_UPDATE.value).update(on=on)

    @staticmethod
    def _set_latest(value: str) -> None:
        Timestamp.objects.filter(key=Timestamp.Choices.CODEX_VERSION.value).update(
            value=value
        )

    @staticmethod
    def _cached_latest() -> str:
        return Timestamp.objects.get(key=Timestamp.Choices.CODEX_VERSION.value).value

    @property
    def _update_tasks(self) -> list:
        return [t for t in self.queue.items if isinstance(t, JanitorCodexUpdateTask)]

    def test_forced_fetch_caches_the_latest_version(self) -> None:
        with patch.object(
            CodexLatestVersionUpdater, "_fetch_latest_version", return_value=_LATEST
        ):
            self.updater.update_latest_version(force=True)
        assert self._cached_latest() == _LATEST

    def test_fetch_queues_an_update_when_auto_update_is_on(self) -> None:
        self._set_auto_update(on=True)
        with patch.object(
            CodexLatestVersionUpdater, "_fetch_latest_version", return_value=_LATEST
        ):
            self.updater.update_latest_version(force=True, update=True)
        assert len(self._update_tasks) == 1

    def test_no_update_when_auto_update_is_off(self) -> None:
        """Off by default, and off means off."""
        self._set_auto_update(on=False)
        with patch.object(
            CodexLatestVersionUpdater, "_fetch_latest_version", return_value=_LATEST
        ):
            self.updater.update_latest_version(force=True, update=True)
        assert not self._update_tasks

    def test_no_update_when_the_fetch_fails(self) -> None:
        """Never update against a version this run could not confirm."""
        self._set_auto_update(on=True)
        self._set_latest("")
        with (
            patch.object(
                CodexLatestVersionUpdater,
                "_fetch_latest_version",
                side_effect=TimeoutError,
            ),
            pytest.raises(TimeoutError),
        ):
            self.updater.update_latest_version(force=True, update=True)
        assert not self._update_tasks
        # A failed fetch starts a cooldown so an outage isn't retried
        # once per request while the cache is empty.
        assert _FetchGate.next_attempt > 0.0

    def test_backoff_skips_an_unforced_fetch(self) -> None:
        self._set_latest("")
        _FetchGate.next_attempt = float("inf")
        with patch.object(CodexLatestVersionUpdater, "_fetch_latest_version") as fetch:
            self.updater.update_latest_version(force=False)
        fetch.assert_not_called()

    def test_in_flight_fetch_is_not_duplicated(self) -> None:
        """Every /api/v4/version hit queues one of these while the cache is empty."""
        self._set_latest("")
        assert _FetchGate.lock.acquire(blocking=False)
        try:
            with patch.object(
                CodexLatestVersionUpdater, "_fetch_latest_version"
            ) as fetch:
                self.updater.update_latest_version(force=True)
            fetch.assert_not_called()
        finally:
            _FetchGate.lock.release()

    def test_fresh_cache_is_not_refetched(self) -> None:
        self._set_latest(_LATEST)
        with patch.object(CodexLatestVersionUpdater, "_fetch_latest_version") as fetch:
            self.updater.update_latest_version(force=False)
        fetch.assert_not_called()

    def _recording_updater(self):
        """Build an updater whose warnings a test can read."""
        log = _RecordingLog()
        return CodexLatestVersionUpdater(log, self.queue, Lock()), log  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    def test_the_daily_check_nags_the_deprecated_image(self) -> None:
        """Bundled here rather than given a janitor job of its own."""
        updater, log = self._recording_updater()
        with (
            patch("codex.util.DOCKER_IMAGE_DEPRECATED", new=True),
            patch.object(
                CodexLatestVersionUpdater, "_fetch_latest_version", return_value=_LATEST
            ),
        ):
            updater.update_latest_version(force=True)
        assert any("ghcr.io/ajslater/codex" in w for w in log.warnings)

    def test_the_daily_check_is_silent_on_every_other_install(self) -> None:
        updater, log = self._recording_updater()
        with patch.object(
            CodexLatestVersionUpdater, "_fetch_latest_version", return_value=_LATEST
        ):
            updater.update_latest_version(force=True)
        assert not log.warnings

    def test_a_cold_cache_cannot_turn_the_nag_into_a_flood(self) -> None:
        """
        Nag once, not once per request.

        While the cache is empty every /api/v4/version hit queues one of
        these. Only the task that wins the fetch gate may log.
        """
        self._set_latest("")
        updater, log = self._recording_updater()
        assert _FetchGate.lock.acquire(blocking=False)
        try:
            with (
                patch("codex.util.DOCKER_IMAGE_DEPRECATED", new=True),
                patch.object(CodexLatestVersionUpdater, "_fetch_latest_version"),
            ):
                updater.update_latest_version(force=True)
        finally:
            _FetchGate.lock.release()
        assert not log.warnings

    def test_a_fresh_cache_is_not_nagged_again(self) -> None:
        """Once a day, not once a request."""
        self._set_latest(_LATEST)
        updater, log = self._recording_updater()
        with patch("codex.util.DOCKER_IMAGE_DEPRECATED", new=True):
            updater.update_latest_version(force=False)
        assert not log.warnings

    def test_locked_database_skips_everything(self) -> None:
        db_write_lock = Lock()
        db_write_lock.acquire()
        try:
            updater = CodexLatestVersionUpdater(logger, self.queue, db_write_lock)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            with patch.object(
                CodexLatestVersionUpdater, "_fetch_latest_version"
            ) as fetch:
                updater.update_latest_version(force=True, update=True)
            fetch.assert_not_called()
        finally:
            db_write_lock.release()
        assert not self._update_tasks

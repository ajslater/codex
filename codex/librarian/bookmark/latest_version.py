"""Fetch the current codex version."""

import json
from datetime import timedelta
from threading import Lock
from time import monotonic
from typing import ClassVar, Final
from urllib.request import urlopen

from django.utils import timezone

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.janitor.status import JanitorCodexLatestVersionStatus
from codex.librarian.scribe.janitor.tasks import JanitorCodexUpdateTask
from codex.librarian.worker import WorkerStatusBase
from codex.models import AdminFlag, Timestamp
from codex.version import PACKAGE_NAME

_REPO_URL: Final = f"https://pypi.python.org/pypi/{PACKAGE_NAME}/json"
_CACHE_EXPIRY: Final = timedelta(days=1) - timedelta(minutes=5)
_REPO_TIMEOUT: Final = 5
_FAILURE_BACKOFF: Final = 600.0


class _FetchGate:
    """
    Process wide guard against stampeding PyPI fetches.

    Every ``CodexLatestVersionTask`` builds a fresh updater on its own
    daemon thread, so this state cannot live on the instance. While the
    cache is empty *every* request to ``/api/v4/version`` queues a fetch
    task, so without the lock a slow or unreachable PyPI means one
    5 second outbound connection per request. ``next_attempt`` adds a
    cooldown after a failure so an outage doesn't retry on every hit.
    """

    lock: ClassVar[Lock] = Lock()
    next_attempt: ClassVar[float] = 0.0


class CodexLatestVersionUpdater(WorkerStatusBase):
    """Methods for fetching the latest version."""

    @staticmethod
    def _fetch_latest_version() -> str:
        """Fetch Latest Remotely."""
        response = urlopen(_REPO_URL, timeout=_REPO_TIMEOUT)
        source = response.read()
        decoded_source = source.decode("utf-8")
        latest_version = json.loads(decoded_source)["info"]["version"]
        if not latest_version:
            reason = "Bad latest version fetched."
            raise ValueError(reason)
        return latest_version

    def _is_fetch_due(self, ts, *, force: bool) -> bool:
        """Is the cached latest version stale enough to refetch."""
        if not (
            force or not ts.value or timezone.now() - ts.updated_at > _CACHE_EXPIRY
        ):
            self.log.debug("Not fetching new latest version, not expired.")
            return False
        if not force and monotonic() < _FetchGate.next_attempt:
            self.log.debug("Not fetching new latest version, waiting after a failure.")
            return False
        return True

    def _fetch_latest_version_into_cache(self, ts, *, force: bool) -> None:
        """Fetch the latest version into the timestamp cache if it's due."""
        if not self._is_fetch_due(ts, force=force):
            return
        if not _FetchGate.lock.acquire(blocking=False):
            self.log.debug("Latest codex version fetch already in flight.")
            return
        try:
            latest_version = self._fetch_latest_version()
        except Exception:
            _FetchGate.next_attempt = monotonic() + _FAILURE_BACKOFF
            raise
        finally:
            _FetchGate.lock.release()
        ts.value = latest_version
        ts.save()
        self.log.info(f"Saved new latest codex version {latest_version}.")

    def _queue_update(self, ts) -> None:
        """Chain into an update task if the admin enabled automatic updates."""
        if not ts.value:
            return
        flag = AdminFlag.objects.only("on").get(key=AdminFlagChoices.AUTO_UPDATE.value)
        if not flag.on:
            self.log.debug("Auto update is disabled, not updating codex.")
            return
        self.librarian_queue.put(JanitorCodexUpdateTask())

    def update_latest_version(self, *, force: bool, update: bool = False) -> None:
        """Get the latest version from a remote repo using a cache."""
        if self.db_write_lock.locked():
            self.log.warning("Database locked, not retrieving latest codex version.")
            return
        status = JanitorCodexLatestVersionStatus()
        try:
            self.status_controller.start(status)
            ts = Timestamp.objects.get(key=Timestamp.Choices.CODEX_VERSION.value)
            self._fetch_latest_version_into_cache(ts, force=force)
            if update:
                # Only after a completed fetch, so the update decision
                # sees the version this run just learned about.
                self._queue_update(ts)
        finally:
            self.status_controller.finish(status)

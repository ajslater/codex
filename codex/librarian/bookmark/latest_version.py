"""Fetch the current codex version."""

import json
from datetime import timedelta

import requests
from django.utils import timezone

from codex.librarian.scribe.janitor.status import JanitorCodexLatestVersionStatus
from codex.librarian.scribe.janitor.tasks import JanitorCodexUpdateTask
from codex.librarian.worker import WorkerStatusBase
from codex.models import Timestamp
from codex.version import PACKAGE_NAME

_PYPI_URL_TEMPLATE = "https://pypi.python.org/pypi/%s/json"
_REPO_URL = _PYPI_URL_TEMPLATE % PACKAGE_NAME
_CACHE_EXPIRY = timedelta(days=1) - timedelta(minutes=5)
_REPO_TIMEOUT = 5


class CodexLatestVersionUpdater(WorkerStatusBase):
    """Methods for fetching the latest version."""

    @staticmethod
    def _fetch_latest_version():
        """Fetch Latest Remotely."""
        response = requests.get(_REPO_URL, timeout=_REPO_TIMEOUT)
        return json.loads(response.text)["info"]["version"]

    def update_latest_version(self, *, force: bool, update: bool = False):
        """Get the latest version from a remote repo using a cache."""
        if self.db_write_lock.locked():
            self.log.warning("Database locked, not retrieving latest codex version.")
            return
        status = JanitorCodexLatestVersionStatus()
        try:
            self.status_controller.start(status)
            ts = Timestamp.objects.get(key=Timestamp.Choices.CODEX_VERSION.value)
            do_fetch = (
                force
                or not ts.version
                or (timezone.now() - ts.updated_at > _CACHE_EXPIRY)
            )
            if do_fetch:
                latest_version = self._fetch_latest_version()
                if not latest_version:
                    reason = "Bad latest version fetched."
                    raise ValueError(reason)
                ts.version = latest_version
                ts.save()
                level = "INFO"
                log_txt = f"Saved new latest codex version {latest_version}."
                if update:
                    task = JanitorCodexUpdateTask()
                    self.librarian_queue.put(task)
            else:
                level = "DEBUG"
                log_txt = "Not fetching new latest version, not expired."
            self.log.log(level, log_txt)
        finally:
            self.status_controller.finish(status)

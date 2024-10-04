"""Fetch the current codex version."""

import json
from datetime import timedelta
from time import time

import requests
from django.utils import timezone

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.models import Timestamp
from codex.status import Status
from codex.version import PACKAGE_NAME
from codex.worker_base import WorkerBaseMixin

_PYPI_URL_TEMPLATE = "https://pypi.python.org/pypi/%s/json"
_REPO_URL = _PYPI_URL_TEMPLATE % PACKAGE_NAME
_CACHE_EXPIRY = timedelta(days=1) - timedelta(minutes=1)
_REPO_TIMEOUT = 5


class LatestVersionMixin(WorkerBaseMixin):
    """Methods for fetching the latest version."""

    @staticmethod
    def _fetch_latest_version():
        """Fetch Latest Remotely."""
        response = requests.get(_REPO_URL, timeout=_REPO_TIMEOUT)
        return json.loads(response.text)["info"]["version"]

    def update_latest_version(self, force=False):
        """Get the latest version from a remote repo using a cache."""
        status = Status(JanitorStatusTypes.CODEX_LATEST_VERSION)
        try:
            self.status_controller.start(status)
            ts = Timestamp.objects.get(
                key=Timestamp.TimestampChoices.CODEX_VERSION.value
            )
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
                self.log.info(f"Saved new latest codex version {latest_version}.")
            else:
                self.log.debug("Not fetching new latest version, not expired.")
        finally:
            self.status_controller.finish(status, until=time() + 2)

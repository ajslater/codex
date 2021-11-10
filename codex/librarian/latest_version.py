"""Determine the latest version of Codex."""
import json

from datetime import timedelta
from logging import getLogger

import requests

from django.utils import timezone

from codex.models import LatestVersion
from codex.version import VERSION


DEFAULT_CACHE_ROOT = "/tmp/"

PYPI_URL_TEMPLATE = "https://pypi.python.org/pypi/%s/json"
CACHE_EXPIRY = timedelta(days=1)
TIMESTAMP_KEY = "timestamp"
REPO_TIMEOUT = 5

LOG = getLogger(__name__)


def _get_version_from_db():
    try:
        lv = LatestVersion.objects.get(pk=LatestVersion.PK)
        expired = timezone.now() - lv.updated_at > CACHE_EXPIRY
        if expired:
            raise LatestVersion.DoesNotExist()
        db_version = lv.version
    except LatestVersion.DoesNotExist:
        db_version = None
    return db_version


def _fetch_latest_version(package_name, repo_url_template=PYPI_URL_TEMPLATE):
    """Fetch Latest Remotely."""
    repo_url = repo_url_template % package_name
    response = requests.get(repo_url, timeout=REPO_TIMEOUT)
    latest_version = json.loads(response.text)["info"]["version"]
    return latest_version


def get_latest_version(
    package_name,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Get the latest version from a remote repo using a cache."""
    latest_version = _get_version_from_db()
    if latest_version is None:
        latest_version = _fetch_latest_version(package_name, repo_url_template)
        LatestVersion.set_version(latest_version)
    return latest_version


def is_outdated(
    package_name,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Is codex outdated."""
    latest_version = get_latest_version(package_name, repo_url_template)

    result = latest_version > VERSION
    log_str = f"{latest_version=} > {VERSION=} = {result}"
    if result:
        LOG.verbose(log_str)  # type: ignore
    else:
        LOG.debug(log_str)

"""Hold the current codex version."""

import json
from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version

import requests
from django.utils import timezone

from codex.logger.logging import get_logger
from codex.models import Timestamp

PACKAGE_NAME = "codex"
PYPI_URL_TEMPLATE = "https://pypi.python.org/pypi/%s/json"
CACHE_EXPIRY = timedelta(days=1)
REPO_TIMEOUT = 5
LOG = get_logger(__name__)


def get_version():
    """Get the current installed codex version."""
    try:
        v = version(PACKAGE_NAME)
    except PackageNotFoundError:
        v = "test"
    return v


VERSION = get_version()


def _get_version_from_db():
    ts = Timestamp.objects.get(key=Timestamp.TimestampChoices.CODEX_VERSION.value)
    expired = timezone.now() - ts.updated_at > CACHE_EXPIRY
    db_version = None if expired else ts.version
    return ts, db_version


def _fetch_latest_version(package_name, repo_url_template=PYPI_URL_TEMPLATE):
    """Fetch Latest Remotely."""
    repo_url = repo_url_template % package_name
    response = requests.get(repo_url, timeout=REPO_TIMEOUT)
    return json.loads(response.text)["info"]["version"]


def get_latest_version(
    package_name,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Get the latest version from a remote repo using a cache."""
    ts, latest_version = _get_version_from_db()
    if latest_version is None:
        try:
            latest_version = _fetch_latest_version(package_name, repo_url_template)
            ts.version = latest_version
            ts.save()
        except Exception:
            LOG.exception("Setting latest codex version in db.")
    return latest_version


def is_outdated(
    package_name,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Is codex outdated."""
    latest_version = get_latest_version(package_name, repo_url_template)

    result = latest_version is not None and latest_version > VERSION
    LOG.info(f"{latest_version=} > {VERSION=} = {result}")

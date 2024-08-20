"""Hold the current codex version."""

import json
from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version

import requests
from django.utils import timezone
from versio.version import Version

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
    db_version = "" if expired else ts.version
    return ts, db_version


def _fetch_latest_version(package_name, repo_url_template=PYPI_URL_TEMPLATE):
    """Fetch Latest Remotely."""
    repo_url = repo_url_template % package_name
    try:
        response = requests.get(repo_url, timeout=REPO_TIMEOUT)
        latest_version = json.loads(response.text)["info"]["version"]
    except Exception as exp:
        LOG.warning(f"Error fetching latest codex version: {exp}")
        latest_version = ""
    return latest_version


def get_latest_version(
    package_name,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Get the latest version from a remote repo using a cache."""
    ts, latest_version = _get_version_from_db()
    if not latest_version:
        latest_version = _fetch_latest_version(package_name, repo_url_template)
        if latest_version:
            ts.version = latest_version
            ts.save()
        else:
            LOG.warning("Latest version not fetched.")
    return latest_version


def is_outdated(
    package_name,
    logger,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Is codex outdated."""
    result = False
    latest_version = get_latest_version(package_name, repo_url_template)
    if not latest_version:
        logger.warning("Unable to determine latest codex version.")
        return result
    versio_latest_version = Version(latest_version)

    installed_versio_version = Version(VERSION)
    if versio_latest_version.parts[1] and not installed_versio_version.parts[1]:  # type: ignore
        pre_blurb = "latest version is a prerelease. But installed version is not."
    else:
        result = versio_latest_version > installed_versio_version
        pre_blurb = ""
    logger.info(f"{latest_version=} > {VERSION=} = {result}{pre_blurb}")
    return result

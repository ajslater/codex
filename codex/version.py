"""Hold the current codex version."""
import json

from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version

import requests

from comicbox.config import get_config
from django.utils import timezone

from codex.models import LatestVersion
from codex.settings.logging import get_logger


PACKAGE_NAME = "codex"
PYPI_URL_TEMPLATE = "https://pypi.python.org/pypi/%s/json"
CACHE_EXPIRY = timedelta(days=1)
REPO_TIMEOUT = 5
LOG = get_logger(__name__)
COMICBOX_CONFIG = get_config(modname=PACKAGE_NAME)


def get_version():
    """Get the current installed codex version."""
    try:
        v = version(PACKAGE_NAME)
    except PackageNotFoundError:
        v = "test"
    return v


VERSION = get_version()


def _get_version_from_db():
    try:
        lv = LatestVersion.objects.get(pk=LatestVersion.CODEX_VERSION_PK)
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
        try:
            latest_version = _fetch_latest_version(package_name, repo_url_template)
            LatestVersion.set_codex_version(latest_version)
        except Exception as exc:
            LOG.error(f"Setting latest codex version in db {exc}")
    return latest_version


def is_outdated(
    package_name,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Is codex outdated."""
    latest_version = get_latest_version(package_name, repo_url_template)

    result = latest_version is not None and latest_version > VERSION
    log_str = f"{latest_version=} > {VERSION=} = {result}"
    if result:
        LOG.verbose(log_str)
    else:
        LOG.debug(log_str)

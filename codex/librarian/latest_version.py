"""Determine the latest version of Codex."""
from datetime import datetime, timedelta
from logging import getLogger
from pathlib import Path

import requests
import simplejson as json

from pkg_resources import get_distribution, parse_version


DEFAULT_CACHE_ROOT = "/tmp/"

PYPI_URL_TEMPLATE = "https://pypi.python.org/pypi/%s/json"
CACHE_EXPIRY = timedelta(days=1)
TIMESTAMP_KEY = "timestamp"
LATEST_VERSION_KEY = "latestVersion"
REPO_TIMEOUT = 5

LOG = getLogger(__name__)


def get_latest_version_from_cache(version_cache_fn):
    """Get from cache."""
    latest_version = None
    try:
        # Get from cache
        with open(version_cache_fn, "r") as cache_file:
            latest = json.loads(cache_file.read())
        timestamp = latest[TIMESTAMP_KEY]
        cache_datetime = datetime.fromtimestamp(timestamp)

        # only use if unexpired
        cache_timedelta = datetime.now() - cache_datetime
        if cache_timedelta < CACHE_EXPIRY:
            latest_version = latest[LATEST_VERSION_KEY]
    except Exception as exc:
        LOG.debug(f"Couldn't get latest version from {version_cache_fn}")
        LOG.debug(str(exc))
    return latest_version


def set_latest_version_to_cache(version_cache_fn, latest_version):
    """Store in cache."""
    try:
        data = {
            TIMESTAMP_KEY: datetime.timestamp(datetime.now()),
            LATEST_VERSION_KEY: latest_version,
        }
        data_str = json.dumps(data)
        with open(version_cache_fn, "w") as cache_file:
            cache_file.write(data_str)
    except Exception as exc:
        LOG.warn(f"Couldn't store latest version at {version_cache_fn}")
        LOG.warn(str(exc))


def get_latest_version(
    package_name,
    cache_root=DEFAULT_CACHE_ROOT,
    repo_url_template=PYPI_URL_TEMPLATE,
    parse=False,
):
    """Get the latest version from a remote repo using a cache."""
    version_cache_fn = Path(cache_root) / f"{package_name}-latest-version.json"

    latest_version = get_latest_version_from_cache(version_cache_fn)

    if latest_version is None:
        # Fetch Latest Remotely
        repo_url = repo_url_template % package_name
        response = requests.get(repo_url, timeout=REPO_TIMEOUT)
        latest_version = json.loads(response.text)["info"]["version"]

    set_latest_version_to_cache(version_cache_fn, latest_version)

    if parse:
        latest_version = parse_version(latest_version)

    return latest_version


def get_installed_version(package_name, parse=False):
    """Get the installed version of a package."""
    distribution = get_distribution(package_name)
    installed_version = distribution.version
    if parse:
        installed_version = parse_version(installed_version)
    return installed_version


def is_outdated(
    package_name,
    cache_root=DEFAULT_CACHE_ROOT,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    """Is codex outdated."""
    installed_version = get_installed_version(package_name, parse=True)
    latest_version = get_latest_version(
        package_name, cache_root, repo_url_template, parse=True
    )

    result = latest_version > installed_version
    LOG.debug(f"{latest_version} > {installed_version} = {result}")


if __name__ == "__main__":
    import sys

    is_outdated(sys.argv[1])

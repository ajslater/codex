from datetime import datetime
from datetime import timedelta
from logging import getLogger
from pathlib import Path

import requests
import simplejson as json

from pkg_resources import get_distribution
from pkg_resources import parse_version


DEFAULT_CACHE_ROOT = "/tmp/"

PYPI_URL_TEMPLATE = "https://pypi.python.org/pypi/%s/json"
CACHE_TIMEDELTA = timedelta(days=1)
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
        if datetime.now() - cache_datetime > CACHE_TIMEDELTA:
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
    package_name, cache_root=DEFAULT_CACHE_ROOT, repo_url_template=PYPI_URL_TEMPLATE
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

    return latest_version


def get_installed_version(package_name):
    """Get the installed version of a package."""
    distribution = get_distribution(package_name)
    return distribution.version


def is_outdated(
    package_name,
    cache_root=DEFAULT_CACHE_ROOT,
    repo_url_template=PYPI_URL_TEMPLATE,
):
    # Installed Version
    installed_version = get_installed_version(package_name)
    parsed_installed_version = parse_version(installed_version)

    # Latest Version
    latest_version = get_latest_version(package_name, cache_root, repo_url_template)
    parsed_latest_version = parse_version(latest_version)

    result = parsed_latest_version > parsed_installed_version
    LOG.debug(f"{parsed_latest_version} > {parsed_installed_version} = {result}")


if __name__ == "__main__":
    import sys

    is_outdated(sys.argv[1])

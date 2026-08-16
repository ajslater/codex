"""Hold the current codex version."""

from importlib.metadata import PackageNotFoundError, version

from packaging.version import InvalidVersion, Version

PACKAGE_NAME = "codex"


def get_version() -> str:
    """Get the current installed codex version."""
    try:
        v = version(PACKAGE_NAME)
    except PackageNotFoundError:
        v = "test"
    return v


VERSION = get_version()


def is_outdated(installed: str, latest: str) -> bool:
    """
    Is the installed version older than the latest published version.

    Pure and total: never raises. Unparseable versions mean "don't
    know", which is reported as not outdated. That covers a source
    checkout (``VERSION == "test"``) and an empty or garbage latest
    version cache, both of which used to raise ``InvalidVersion`` from
    the janitor's update check.
    """
    if not installed or not latest:
        return False
    try:
        installed_version = Version(installed)
        latest_version = Version(latest)
    except InvalidVersion:
        return False
    if latest_version.is_prerelease and not installed_version.is_prerelease:
        # Never auto-advance a stable install onto a prerelease.
        return False
    return latest_version > installed_version

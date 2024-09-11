"""Hold the current codex version."""

from importlib.metadata import PackageNotFoundError, version

PACKAGE_NAME = "codex"


def get_version():
    """Get the current installed codex version."""
    try:
        v = version(PACKAGE_NAME)
    except PackageNotFoundError:
        v = "test"
    return v


VERSION = get_version()

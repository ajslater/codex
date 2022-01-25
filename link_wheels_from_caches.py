#!/usr/bin/env python3
"""Harvest wheels from pip & poetry caches and create a repo from them."""
import os
import platform

from pathlib import Path


CACHE_WHEELS_PATH = Path("./cache/packages/wheels")
LINUX_CACHE_PATH = ".cache"
MACOS_CACHE_PATH = "Library/Caches"


def get_cache_path():
    """Get the system cache path."""
    path = Path.home()
    system = platform.system()
    if system == "Darwin":
        path = path / MACOS_CACHE_PATH
    else:  # system == "Linux":
        path = path / LINUX_CACHE_PATH
    return path


def get_poetry_artifacts_path():
    """Get the poetry cache artifacts path."""
    cache_path = get_cache_path()
    return cache_path / "pypoetry/artifacts"


def get_pip_wheels_path():
    """Get the pip cache wheels path."""
    cache_path = get_cache_path()
    return cache_path / "pip/wheels"


def link_artifact(cached_artifact_path):
    """Link an artifact in the cache tree into the wheels directory."""
    link_path = CACHE_WHEELS_PATH / cached_artifact_path.name
    link_path.unlink(missing_ok=True)
    link_path.symlink_to(cached_artifact_path)
    print(".", end="")


def link_cached_dir(dir_name):
    """Recursively link artifacts in a cached artifacts subdir."""
    for root_dirname, _, filenames in os.walk(dir_name):
        root_path = Path(root_dirname)
        for filename in filenames:
            full_path = root_path / filename
            if full_path.is_dir():
                link_cached_dir(full_path)
                continue
            link_artifact(full_path)


def link_cached_artifacts():
    """Link all the cached poetry artifacts into the wheels dir."""
    print("Linking cached artifacts from ", end="")
    CACHE_WHEELS_PATH.mkdir(parents=True, exist_ok=True)
    print("poetry", end="")
    poetry_artifacts_path = get_poetry_artifacts_path()
    link_cached_dir(poetry_artifacts_path)
    print("pip", end="")
    pip_wheels_path = get_poetry_artifacts_path()
    link_cached_dir(pip_wheels_path)
    print("done.")


def main():
    """Copy the wheels and build the repo."""
    link_cached_artifacts()


if __name__ == "__main__":
    main()

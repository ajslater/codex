#!/usr/bin/env python3
"""Harvest wheels from pip & poetry caches and create a repo from them."""
import os

from pathlib import Path

from cache_paths import PIP_WHEELS_PATH, POETRY_ARTIFACTS_PATH


CACHE_WHEELS_PATH = Path("./cache/packages/wheels")


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
    link_cached_dir(POETRY_ARTIFACTS_PATH)
    print("pip", end="")
    link_cached_dir(PIP_WHEELS_PATH)
    print("done.")


def main():
    """Copy the wheels and build the repo."""
    link_cached_artifacts()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Harvest wheels from pip & poetry caches and create a repo from them."""
import os
import sys
from pathlib import Path
from shutil import copy

from cache_paths import PIP_WHEELS_PATH, POETRY_ARTIFACTS_PATH

CACHE_WHEELS_PATH = Path("./cache/packages/wheels")


def link_artifact(cached_artifact_path, copy_files):
    """Link an artifact in the cache tree into the wheels directory."""
    dest_path = CACHE_WHEELS_PATH / cached_artifact_path.name
    dest_path.unlink(missing_ok=True)
    if copy_files:
        copy(cached_artifact_path, dest_path)
    else:
        dest_path.symlink_to(cached_artifact_path)
    print(".", end="")


def link_cached_dir(dir_name, copy_files):
    """Recursively link artifacts in a cached artifacts subdir."""
    for root_dirname, _, filenames in os.walk(dir_name):
        root_path = Path(root_dirname)
        for filename in filenames:
            full_path = root_path / filename
            if full_path.is_dir():
                link_cached_dir(full_path, copy_files)
                continue
            link_artifact(full_path, copy_files)


def link_cached_artifacts(copy_files):
    """Link all the cached poetry artifacts into the wheels dir."""
    print("Linking cached artifacts from ", end="")
    CACHE_WHEELS_PATH.mkdir(parents=True, exist_ok=True)
    print("poetry", end="")
    link_cached_dir(POETRY_ARTIFACTS_PATH, copy_files)
    print("pip", end="")
    link_cached_dir(PIP_WHEELS_PATH, copy_files)
    print("done.")


def main(args):
    """Copy the wheels and build the repo."""
    copy_files = "copy" in args
    link_cached_artifacts(copy_files)


if __name__ == "__main__":
    main(sys.argv[1:])

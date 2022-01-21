#!/usr/bin/env python3
"""Harvest wheels from pip & poetry caches and create a repo from them."""
import os
import subprocess

from pathlib import Path
from shutil import copy, copytree


KEEP_PHRASES = ("cryptography",)


def run(args):
    """Run process and return lines array."""
    proc = subprocess.run(args, capture_output=True, check=True, text=True)
    return proc.stdout.split("\n")


# START POETRY PRUNE


def get_installed_artifacts():
    """Get the list of installed poetry artifacts."""
    lines = run(("poetry", "run", "pip3", "freeze"))
    installed_artifacts = set()
    for line in lines:
        artifact_fn = line.split(" @ file://")[-1]
        installed_artifacts.add(artifact_fn.strip())
    return installed_artifacts


def remove_poetry_artifact(full_path, artifacts_path):
    """Remove a single poetry artifact and its containing directories."""
    full_path.unlink()
    try:
        for dir_path in full_path.parents:
            if dir_path.is_relative_to(artifacts_path):
                dir_path.rmdir()
            else:
                break
    except OSError:
        pass
    print(f"Pruned {full_path.name}")


def prune_dir(artifacts_path, dir_path, installed_artifacts):
    """Recursively prune a poetry artifact subdirectory."""
    for root_dirname, _, filenames in os.walk(dir_path):
        root_path = Path(root_dirname)
        for filename in filenames:
            full_path = root_path / filename
            if full_path.is_dir():
                prune_dir(artifacts_path, full_path, installed_artifacts)
                continue
            full_path_str = str(full_path)
            if full_path_str in installed_artifacts:
                continue
            for phrase in KEEP_PHRASES:
                if phrase in full_path_str:
                    print(f"Not pruning package with phrase: {phrase}")
                    continue
            remove_poetry_artifact(full_path, artifacts_path)


def get_poetry_artifacts_path():
    """Get the poetry cache artifacts path."""
    artifacts_dirname = run(("poetry", "config", "cache-dir"))[0]
    return Path(artifacts_dirname) / "artifacts"


def prune_poetry_artifacts():
    """Prune all not installed poetry cache artifacts."""
    artifacts_path = get_poetry_artifacts_path()
    installed_artifacts = get_installed_artifacts()
    prune_dir(artifacts_path, artifacts_path, installed_artifacts)


# END POETRY PRUNE ###
# START POETRY COPY & LINK ####


def copy_poetry_artifacts(cache_path, artifacts_path=None):
    """Copy poetry artifacts tree into the cache path."""
    if artifacts_path is None:
        artifacts_path = get_poetry_artifacts_path()
    cache_path.mkdir(parents=True, exist_ok=True)
    dest = cache_path / artifacts_path.name
    copytree(artifacts_path, dest)
    print("Copied poetry artifacts cache.")


def link_artifact(cache_path, cached_artifact_path, cache_wheels_path):
    """Link an artifact in the cache tree into the wheels directory."""
    link_path = cache_wheels_path / cached_artifact_path.name
    relative_path = ".." / cached_artifact_path.relative_to(cache_path)
    link_path.symlink_to(relative_path)
    print(".", end="")


def link_cached_poetry_dir(cache_path, dir_name, cache_wheels_path):
    """Recursively link artifacts in a cached artifacts subdir."""
    for root_dirname, _, filenames in os.walk(dir_name):
        root_path = Path(root_dirname)
        for filename in filenames:
            full_path = root_path / filename
            if full_path.is_dir():
                link_cached_poetry_dir(cache_path, full_path, cache_wheels_path)
                continue
            link_artifact(cache_path, full_path, cache_wheels_path)


def link_cached_poetry_artifacts(cache_path, cache_wheels_path):
    """Link all the cached poetry artifacts into the wheels dir."""
    print("Linking cached poetry artifacts", end="")
    cached_artifacts_path = cache_path / "artifacts"
    cache_wheels_path.mkdir(parents=True, exist_ok=True)
    link_cached_poetry_dir(cache_path, cached_artifacts_path, cache_wheels_path)
    print("done.")


# END POETRY COPY & LINK ####
# START PIP COPY ####


def copy_wheels(root_path, wheels_path):
    """Copy wheels from the root_path into the wheels path."""
    print(f"Copy wheels from {root_path}", end="")
    wheels_path.mkdir(parents=True, exist_ok=True)
    for rootname, _, filenames in os.walk(root_path):
        root_path = Path(rootname)
        for filename in filenames:
            full_path = root_path / filename
            if full_path.is_dir():
                copy_wheels(root_path, wheels_path)
            if filename.endswith(".whl"):
                dest_path = wheels_path / filename
                dest_path.unlink(missing_ok=True)
                copy(full_path, wheels_path)
                print(".", end="")
    print("done.")


def copy_program_wheels(args, program_wheels_subdir, cache_wheels_path):
    """Copy wheels using a program to find the root."""
    program_cache_dirname = run(args)[0]
    program_cache_path = Path(program_cache_dirname) / program_wheels_subdir
    copy_wheels(program_cache_path, cache_wheels_path)


# END PIP COPY ####


def main(cache_dirname):
    """Copy the wheels and build the repo."""
    cache_path = Path(cache_dirname)
    prune_poetry_artifacts()
    copy_poetry_artifacts(cache_path)
    cache_wheels_path = cache_path / "wheels"
    link_cached_poetry_artifacts(cache_path, cache_wheels_path)
    copy_program_wheels(("pip", "cache", "dir"), "wheels", cache_wheels_path)


if __name__ == "__main__":
    import sys

    main(sys.argv[1])

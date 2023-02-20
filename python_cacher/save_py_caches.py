#!/usr/bin/env python3
"""Copy pip & poetry user caches to a volume saved location."""
import os
import subprocess
import sys
from pathlib import Path
from shutil import copytree

from cache_paths import PIP_CACHE_PATH, POETRY_ARTIFACTS_PATH, POETRY_CACHE_PATH

CACHE_PATH = Path("./cache/packages")

KEEP_PHRASES = ("cryptography",)


def run(args):
    """Run process and return lines array."""
    proc = subprocess.run(args, capture_output=True, check=True, text=True)
    return proc.stdout.split("\n")


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
    count = 0
    for root_dirname, _, filenames in os.walk(dir_path):
        root_path = Path(root_dirname)
        for filename in filenames:
            full_path = root_path / filename
            if full_path.is_dir():
                count += prune_dir(artifacts_path, full_path, installed_artifacts)
                continue
            full_path_str = str(full_path)
            if full_path_str in installed_artifacts:
                continue
            for phrase in KEEP_PHRASES:
                if phrase in full_path_str:
                    print(f"Not pruning package with phrase: {phrase}")
                    continue
            remove_poetry_artifact(full_path, artifacts_path)
            count += 1
    return count


def prune_poetry_artifacts():
    """Prune all not installed poetry cache artifacts."""
    installed_artifacts = get_installed_artifacts()
    count = prune_dir(POETRY_ARTIFACTS_PATH, POETRY_ARTIFACTS_PATH, installed_artifacts)
    print(f"Pruned {count} poetry artifacts.")


def save_cache(native_cache_path, arch_cache_path):
    """Save a python cache to the architecture specific cache path."""
    dest = arch_cache_path / native_cache_path.name
    copytree(
        native_cache_path,
        dest,
        dirs_exist_ok=True,
    )
    print(f"Copied {native_cache_path} to {dest}")


def main(args):
    """Prune the poetry cache and then copy poetry & pip cache."""
    arch = run(("uname", "-m"))[0]
    arch_cache_path = CACHE_PATH / arch
    arch_cache_path.mkdir(parents=True, exist_ok=True)
    if "poetry" in args:
        if "prune" in args:
            prune_poetry_artifacts()
        save_cache(POETRY_CACHE_PATH, arch_cache_path)
    if "pip" in args:
        save_cache(PIP_CACHE_PATH, arch_cache_path)


if __name__ == "__main__":
    main(sys.argv[1:])

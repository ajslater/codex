#!/usr/bin/env python3
"""Copy pip & poetry user caches to a volume saved location."""
import os
import subprocess

from pathlib import Path
from shutil import copytree


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
    cache_dirname = run(("poetry", "config", "cache-dir"))[0]
    return Path(cache_dirname) / "artifacts"


def prune_poetry_artifacts():
    """Prune all not installed poetry cache artifacts."""
    artifacts_path = get_poetry_artifacts_path()
    installed_artifacts = get_installed_artifacts()
    prune_dir(artifacts_path, artifacts_path, installed_artifacts)


def main():
    """Prune the poetry cache and then copy poetry & pip cache."""
    poetry_cache_path = Path(run(("poetry", "config", "cache-dir"))[0])
    prune_poetry_artifacts()
    pip_cache_path = Path(run(("pip3", "cache", "dir"))[0])
    arch = run(("uname", "-m"))[0]
    arch_cache_path = CACHE_PATH / arch
    arch_cache_path.mkdir(parents=True, exist_ok=True)
    copytree(
        poetry_cache_path, arch_cache_path / poetry_cache_path.name, dirs_exist_ok=True
    )
    copytree(pip_cache_path, arch_cache_path / pip_cache_path.name, dirs_exist_ok=True)


if __name__ == "__main__":
    main()

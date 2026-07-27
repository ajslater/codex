#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRUNE = frozenset({"build", "dist", "docs", "node_modules", "test", "tests"})


def _from_pyproject() -> str | None:
    """Read an explicitly configured settings module."""
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.is_file():
        return None
    with pyproject.open("rb") as f:
        config = tomllib.load(f)
    return config.get("tool", {}).get("devenv", {}).get("django-settings-module")


def _is_settings_package(pkg: Path) -> bool:
    """Test if a dir is a package that holds a settings module or package."""
    if (
        not pkg.is_dir()
        or pkg.name.startswith((".", "_"))
        or pkg.name in PRUNE
        or not (pkg / "__init__.py").is_file()
    ):
        return False
    return (pkg / "settings.py").is_file() or (
        pkg / "settings" / "__init__.py"
    ).is_file()


def _discover() -> str:
    """Find the sole <package>/settings module or package in the project root."""
    candidates = sorted(pkg.name for pkg in ROOT.iterdir() if _is_settings_package(pkg))
    if len(candidates) == 1:
        return f"{candidates[0]}.settings"
    reason = (
        f"Found {len(candidates)} django settings modules in {ROOT}: {candidates}. "
        "Set [tool.devenv] django-settings-module in pyproject.toml."
    )
    raise RuntimeError(reason)


def main():
    """Run the server."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", _from_pyproject() or _discover())
    try:
        from django.core.management import (
            execute_from_command_line,
        )
    except ImportError as exc:
        reason = (
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        )
        raise ImportError(reason) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

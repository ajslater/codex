#!/usr/bin/env python3
"""
Check shell scripts recursively for a descriptive comment on line 2.

Detects shell scripts by shebang.
Inspired by @defunctzombie
"""

from __future__ import annotations

import os
import re
import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from pathlib import Path
from typing import TYPE_CHECKING

from pathspec import PathSpec

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHELL_SHEBANG_PATTERN: re.Pattern[str] = re.compile(r"^#!.*sh")

# Patterns that are always excluded regardless of an ignore file.
DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    ".*",  # hidden files / directories
    "*~",  # editor backup files
]

COMMENT_PATTERN: re.Pattern[str] = re.compile(r"^#+.{4}")

# Number of bytes to read when sniffing the shebang — avoids loading huge
# binary files into memory.
SHEBANG_READ_BYTES: int = 512


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_ignore_spec(ignore_path: Path | None) -> PathSpec:
    """Return a gitignore style PathSpec built from *ignore_path* plus the built-in defaults."""
    lines: list[str] = list(DEFAULT_EXCLUDE_PATTERNS)

    if ignore_path is not None:
        lines += ignore_path.read_text(encoding="utf-8").splitlines()

    return PathSpec.from_lines("gitwildmatch", lines)


def read_first_two_lines(path: Path) -> tuple[str, str]:
    """Return the first two lines of *path* as a (line1, line2) tuple."""
    try:
        with path.open("rb") as fh:
            raw = fh.read(SHEBANG_READ_BYTES)
    except OSError:
        return "", ""

    lines = raw.decode("utf-8", errors="replace").splitlines()
    line1 = lines[0] if len(lines) > 0 else ""
    line2 = lines[1] if len(lines) > 1 else ""
    return line1, line2


def is_shell_script(line1: str) -> bool:
    """Return True when *line1* looks like a shell shebang."""
    return bool(SHELL_SHEBANG_PATTERN.search(line1))


def has_description_comment(line2: str) -> bool:
    """Return True when *line2* starts with a ``# `` comment."""
    return bool(COMMENT_PATTERN.match(line2))


def _walk_tree(root: Path, spec: PathSpec) -> Generator[Path]:
    """
    Yield every file under *root* not excluded by *spec*.

    Uses ``os.scandir`` and prunes ignored directories without descending into
    them — important when trees like ``.git`` or ``node_modules`` are excluded.
    """
    root_str = str(root)
    stack: list[str] = [root_str]
    while stack:
        current = stack.pop()
        try:
            scanner = os.scandir(current)
        except OSError:
            continue
        with scanner:
            for entry in scanner:
                rel = os.path.relpath(entry.path, root_str)
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if not spec.match_file(rel + "/"):
                            stack.append(entry.path)
                    elif entry.is_file() and not spec.match_file(rel):
                        yield Path(entry.path)
                except OSError:
                    continue


def iter_files(path_strs: Sequence[str], spec: PathSpec) -> Generator[Path]:
    """
    Yield every file under *path_strs* that is not excluded by *spec*.

    Each candidate path is tested relative to the root it was found under so
    that gitignore-style directory patterns (e.g. ``vendor/``) work correctly.
    """
    for path_str in path_strs:
        path = Path(path_str)
        if not path.exists():
            print(f"👎  Path does not exist: {path}", file=sys.stderr)  # noqa: T201
            sys.exit(2)

        root = path.resolve()
        if root.is_file():
            if not spec.match_file(root.name):
                yield root
            continue

        yield from _walk_tree(root, spec)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> ArgumentParser:
    """Build cli arg parser."""
    parser = ArgumentParser(
        description="Find shell scripts that are missing a descriptive comment on line 2.",
        formatter_class=RawDescriptionHelpFormatter,
        epilog=(
            "Exit status: 0 if all shell scripts pass, 1 if any are missing\n"
            "a comment on line 2, 2 on usage / IO errors."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="Files or directories to examine.",
    )
    parser.add_argument(
        "-i",
        "--ignore-file",
        metavar="FILE",
        help="Ignore-file with gitignore-style patterns (e.g. .zombieignore).",
    )
    return parser


def _parse_ignore_file(args: Namespace) -> PathSpec:
    ignore_path: Path | None = None
    if args.ignore_file:
        ignore_path = Path(args.ignore_file)
        if not ignore_path.is_file():
            print(f"👎  Can't read ignore file: {ignore_path}", file=sys.stderr)  # noqa: T201
            sys.exit(2)

    try:
        return build_ignore_spec(ignore_path)
    except OSError as exc:
        print(f"👎  Failed to parse ignore file: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(2)


def main() -> None:
    """Run program."""
    parser = build_parser()
    args = parser.parse_args()
    spec = _parse_ignore_file(args)

    offenders: list[Path] = []

    for path in iter_files(args.paths, spec):
        line1, line2 = read_first_two_lines(path)

        if not is_shell_script(line1):
            continue

        if not has_description_comment(line2):
            print(f"🔪  {path}")  # noqa: T201
            offenders.append(path)

    if offenders:
        print(  # noqa: T201
            f"\n{len(offenders)} script(s) missing a description comment.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("👍")  # noqa: T201


if __name__ == "__main__":
    main()

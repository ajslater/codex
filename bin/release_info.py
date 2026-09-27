#!/usr/bin/env python3
"""
Read the facts of a release from pyproject.toml and NEWS.md.

bin/release-tag.sh calls this for the version, the tag, the release title and
the release notes, so the CI release job and a local run agree.

  info       Print version=, tag=, final= and title= lines, and write the
             version's NEWS.md section to --notes-file.
  is-latest  Read `git ls-remote --tags --refs` lines on stdin. Print true
             when --version is a final release at least as new as every
             final vX.Y.Z tag listed, otherwise false.

Standard library only, so the release job needs no virtualenv. Content errors
exit 2.
"""

from __future__ import annotations

import os
import re
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Iterable, Iterator, Sequence

# The same rules ci.yml uses to read the version and to call it final.
VERSION_RE: Final = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)
FINAL_RE: Final = re.compile(r"\d+\.\d+\.\d+")
# "## v2.4.0" or "## v2.4.0 - Read State & Match Review".
HEADER_RE: Final = re.compile(r"^## v(?P<ver>\S+?)(?: - (?P<sub>.+?))?\s*$")
FINAL_TAG_RE: Final = re.compile(r"refs/tags/v(\d+)\.(\d+)\.(\d+)")
SECTION_PREFIX: Final = "## "
FENCE_PREFIX: Final = "```"
EXIT_CONTENT_ERROR: Final = 2


class ReleaseInfoError(Exception):
    """The release content is missing, ambiguous or inconsistent."""


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    """What a release is called and what its notes say."""

    version: str
    final: bool
    title: str
    notes: str

    @property
    def tag(self) -> str:
        """Return the git tag for this version."""
        return f"v{self.version}"

    def fields(self) -> dict[str, str]:
        """Return the key=value facts bin/release-tag.sh reads."""
        return {
            "version": self.version,
            "tag": self.tag,
            "final": "true" if self.final else "false",
            "title": self.title,
        }


def is_final(version: str) -> bool:
    """Whether the version is a final X.Y.Z release rather than an alpha."""
    return FINAL_RE.fullmatch(version) is not None


def read_version(pyproject: str) -> str:
    """Return the project version from pyproject.toml."""
    match = VERSION_RE.search(pyproject)
    if not match:
        reason = 'pyproject.toml has no version = "..." line'
        raise ReleaseInfoError(reason)
    return match.group(1)


def section_starts(lines: Sequence[str]) -> Iterator[int]:
    """Yield the index of every level-two heading outside a code fence."""
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith(FENCE_PREFIX):
            in_fence = not in_fence
        elif not in_fence and line.startswith(SECTION_PREFIX):
            yield index


def _trim_blank_lines(lines: Sequence[str]) -> str:
    """Join the lines, dropping blank lines at either end only."""
    kept = list(lines)
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def find_section(news: str, version: str) -> tuple[str, str] | None:
    """
    Return the (subtitle, body) of the version's NEWS section, or None.

    The version must match exactly, so 2.4.1 never finds 2.4.10 or 2.4.1a1.
    The body runs to the next level-two heading or the end of the file.
    """
    lines = news.split("\n")
    starts = list(section_starts(lines))
    found: list[tuple[int, str]] = []
    for start in starts:
        match = HEADER_RE.match(lines[start])
        if match and match["ver"] == version:
            found.append((start, match["sub"] or ""))
    if len(found) > 1:
        reason = f"NEWS.md has {len(found)} sections for v{version}"
        raise ReleaseInfoError(reason)
    if not found:
        return None
    start, subtitle = found[0]
    end = next((later for later in starts if later > start), len(lines))
    return subtitle, _trim_blank_lines(lines[start + 1 : end])


def build_info(pyproject: str, news: str, expected: str | None = None) -> ReleaseInfo:
    """Work out the release from the file contents at the release commit."""
    version = read_version(pyproject)
    if expected is not None and expected.removeprefix("v") != version:
        reason = f"pyproject.toml says {version}, not {expected}"
        raise ReleaseInfoError(reason)
    final = is_final(version)
    subtitle, body = find_section(news, version) or ("", "")
    if not body and final:
        reason = f"NEWS.md needs a non-empty '## v{version}' section for this release"
        raise ReleaseInfoError(reason)
    title = f"v{version} - {subtitle}" if subtitle else f"v{version}"
    notes = (body or f"Pre-release v{version}") + "\n"
    return ReleaseInfo(version=version, final=final, title=title, notes=notes)


def _final_tag_versions(ls_remote: Iterable[str]) -> Iterator[tuple[int, ...]]:
    """Yield the version of every final vX.Y.Z tag in ls-remote output."""
    for line in ls_remote:
        fields = line.split()
        match = FINAL_TAG_RE.fullmatch(fields[-1]) if fields else None
        if match:
            yield tuple(int(part) for part in match.groups())


def is_latest(version: str, ls_remote: Iterable[str]) -> bool:
    """Whether the version is final and no final tag is newer."""
    version = version.removeprefix("v")
    if not is_final(version):
        return False
    mine = tuple(int(part) for part in version.split("."))
    return all(mine >= other for other in _final_tag_versions(ls_remote))


def _read(path: Path) -> str:
    # Bytes, not text mode, so line endings reach the notes unchanged.
    return path.read_bytes().decode("utf-8")


def _run_info(args: Namespace) -> None:
    info = build_info(_read(args.pyproject), _read(args.news), args.version)
    args.notes_file.write_bytes(info.notes.encode("utf-8"))
    lines = "".join(f"{key}={value}\n" for key, value in info.fields().items())
    sys.stdout.write(lines)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(lines)


def _error(message: str) -> None:
    prefix = "::error::" if os.environ.get("GITHUB_ACTIONS") == "true" else "ERROR: "
    print(f"{prefix}{message}", file=sys.stderr)


def build_parser() -> ArgumentParser:
    """Build the command line parser."""
    parser = ArgumentParser(
        description=__doc__, formatter_class=RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    info = commands.add_parser("info", help="version, tag, title and notes")
    info.add_argument("--pyproject", type=Path, required=True)
    info.add_argument("--news", type=Path, required=True)
    info.add_argument("--notes-file", type=Path, required=True)
    info.add_argument(
        "--version", help="fail unless pyproject.toml has this version (v optional)"
    )
    info.add_argument(
        "--github-output", type=Path, help="also append the facts to this file"
    )
    latest = commands.add_parser("is-latest", help="is this the newest final?")
    latest.add_argument("--version", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return the exit status."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "info":
            _run_info(args)
        else:
            print("true" if is_latest(args.version, sys.stdin) else "false")
    except (ReleaseInfoError, OSError, UnicodeDecodeError) as exc:
        _error(str(exc))
        return EXIT_CONTENT_ERROR
    return 0


if __name__ == "__main__":
    sys.exit(main())

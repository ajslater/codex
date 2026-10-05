"""
Invariants of the production image in the Dockerfile.

The final image is python-debian plus three apt packages plus one venv at
/opt/codex built in the wheel-installer stage. Each test pins a mistake that
once shipped: an apt name apt read as a regex and answered with a second
Python, a copy of the whole builder /usr/local, and a bytecode purge that made
every process recompile on import. CI's image build only runs on deploy, so
these are the only Dockerfile checks a PR gets.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"
_FINAL_APT = ("curl", "libstdc++6", "unrar")
_VENV = "/opt/codex"
# apt treats a name holding any of these as a regex when nothing matches it
# exactly: "ruamel.yaml.clib" installed python3-ruamel.yaml.clib and with it
# Debian's whole python3.
_APT_REGEX_CHARS = re.compile(r"[.?*]")
_FROM_RE = re.compile(r"FROM\s+\S+\s+AS\s+(\S+)", re.IGNORECASE)
_PYC_PURGE_RE = re.compile(r"-name\s+['\"]?(?:__pycache__|\*\.py[co])")


def _instructions(text: str) -> list[tuple[str, str]]:
    """Return (keyword, arguments) per instruction, continuations joined."""
    instructions: list[tuple[str, str]] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        keyword, _, args = (pending + line).partition(" ")
        instructions.append((keyword.upper(), args.strip()))
        pending = ""
    return instructions


@pytest.fixture(scope="module")
def stages() -> dict[str, list[tuple[str, str]]]:
    """Return each named stage's instructions, FROM excluded."""
    found: dict[str, list[tuple[str, str]]] = {}
    current: list[tuple[str, str]] = []
    for keyword, args in _instructions(_DOCKERFILE.read_text(encoding="utf-8")):
        if keyword == "FROM":
            current = []
            if match := _FROM_RE.fullmatch(f"FROM {args}"):
                found[match.group(1)] = current
            continue
        current.append((keyword, args))
    return found


def _runs(instructions: list[tuple[str, str]]) -> list[str]:
    return [args for keyword, args in instructions if keyword == "RUN"]


def _apt_packages(run: str) -> list[str]:
    packages: list[str] = []
    for command in run.split("&&"):
        words = command.split()
        if words[:2] == ["apt-get", "install"]:
            packages += [word for word in words[2:] if not word.startswith("-")]
    return packages


def test_final_apt_packages(stages: dict[str, list[tuple[str, str]]]) -> None:
    """Wheels bundle the image codecs and libyaml; only these are left."""
    packages = [pkg for run in _runs(stages["final"]) for pkg in _apt_packages(run)]
    assert tuple(packages) == _FINAL_APT


def test_no_apt_package_is_a_regex(stages: dict[str, list[tuple[str, str]]]) -> None:
    """A dot in an apt name selects every package the regex matches."""
    packages = [
        pkg
        for instructions in stages.values()
        for run in _runs(instructions)
        for pkg in _apt_packages(run)
    ]
    assert packages
    assert [pkg for pkg in packages if _APT_REGEX_CHARS.search(pkg)] == []


def test_final_copies_only_the_venv(stages: dict[str, list[tuple[str, str]]]) -> None:
    """Copying the builder's /usr/local shipped node, uv, pip and poetry."""
    copies = [
        args.split()
        for keyword, args in stages["final"]
        if keyword == "COPY" and args.startswith("--from=")
    ]
    assert copies == [["--from=wheel-installer", _VENV, _VENV]]


def test_bytecode_is_kept(stages: dict[str, list[tuple[str, str]]]) -> None:
    """The app runs as abc, which can't write a .pyc, so ship them compiled."""
    runs = [run for instructions in stages.values() for run in _runs(instructions)]
    assert [run for run in runs if _PYC_PURGE_RE.search(run)] == []
    installs = [
        command
        for run in _runs(stages["wheel-installer"])
        for command in run.split("&&")
        if "uv pip install" in command
    ]
    assert installs
    assert all("--compile-bytecode" in command for command in installs)

"""
Golden tests: bin/release_info.py against codex's real NEWS.md.

The release job builds each GitHub Release from NEWS.md through
bin/release_info.py, so these pin the titles and bodies already published.
bin/release_info.py itself is devenv's and is tested there.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "bin" / "release_info.py"
_SPEC = importlib.util.spec_from_file_location("release_info", _SCRIPT)
assert _SPEC
assert _SPEC.loader
release_info = importlib.util.module_from_spec(_SPEC)
# dataclasses resolve their module through sys.modules while the class is built.
sys.modules[_SPEC.name] = release_info
_SPEC.loader.exec_module(release_info)


def _pyproject(version: str) -> str:
    return (
        f'[tool.ruff]\ntarget-version = "py312"\n\n[project]\nversion = "{version}"\n'
    )


_REAL_NEWS = (_ROOT / "NEWS.md").read_text(encoding="utf-8")


def test_golden_v2_4_0_title() -> None:
    """The published v2.4.0 release title."""
    info = release_info.build_info(_pyproject("2.4.0"), _REAL_NEWS)
    assert info.title == "v2.4.0 - Read State & Match Review"


def test_golden_v2_4_1_body() -> None:
    """The published v2.4.1 release body."""
    info = release_info.build_info(_pyproject("2.4.1"), _REAL_NEWS)
    assert info.title == "v2.4.1"
    assert info.notes == (
        "- Fixes\n"
        "    - The browser pane was unable to scroll due to an upstream widget bug.\n"
    )


def test_golden_every_header_since_v2_parses() -> None:
    """Every '## v' header from v2.0.0 on names one final version, once."""
    lines = _REAL_NEWS.split("\n")
    versions: list[str] = []
    for start in release_info.section_starts(lines):
        match = release_info.HEADER_RE.match(lines[start])
        assert match, lines[start]
        versions.append(match["ver"])
        if match["ver"] == "2.0.0":
            break
    else:
        pytest.fail("NEWS.md has no ## v2.0.0 section")
    assert all(release_info.is_final(version) for version in versions)
    for version in versions:
        release_info.build_info(_pyproject(version), _REAL_NEWS)

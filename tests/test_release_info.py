"""
bin/release_info.py: version, title and notes for a release.

The release job builds the GitHub Release from these, so the golden tests
read the real NEWS.md and pin the titles and bodies already published.
"""

from __future__ import annotations

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

ReleaseInfoError = release_info.ReleaseInfoError

_NEWS = """\
# 📜 Codex News

## v1.2.10

- Ten

## v1.2.3 - Sub & Title

- Features
    - Nested bullet kept exactly.

    - After an internal blank line.
# An H1 does not end the section
  ## An indented heading does not end it either
### Nor does a level three heading

```
## v9.9.9
```

## v1.2.3a1

- Alpha

## v1.2.2

- Oldest, running to the end of the file


"""


def _pyproject(version: str) -> str:
    return (
        f'[tool.ruff]\ntarget-version = "py312"\n\n[project]\nversion = "{version}"\n'
    )


# ---------------------------------------------------------------------------
# Headers, section bounds and version matching
# ---------------------------------------------------------------------------


def test_bare_header_title() -> None:
    """A header without a subtitle gives the title vX.Y.Z."""
    info = release_info.build_info(_pyproject("1.2.10"), _NEWS)
    assert info.title == "v1.2.10"
    assert info.tag == "v1.2.10"
    assert info.notes == "- Ten\n"


def test_subtitle_header_title() -> None:
    """A subtitle joins the title with ' - ' and keeps its ampersand."""
    info = release_info.build_info(_pyproject("1.2.3"), _NEWS)
    assert info.title == "v1.2.3 - Sub & Title"


def test_section_bounds_and_whitespace() -> None:
    """Only the next '## ' ends a section; inner blanks and indents survive."""
    section = release_info.find_section(_NEWS, "1.2.3")
    assert section is not None
    _, body = section
    assert body == (
        "- Features\n"
        "    - Nested bullet kept exactly.\n"
        "\n"
        "    - After an internal blank line.\n"
        "# An H1 does not end the section\n"
        "  ## An indented heading does not end it either\n"
        "### Nor does a level three heading\n"
        "\n"
        "```\n"
        "## v9.9.9\n"
        "```"
    )


def test_heading_inside_fence_is_ignored() -> None:
    """A '## v' line inside a code fence is not a section."""
    assert release_info.find_section(_NEWS, "9.9.9") is None


def test_last_section_runs_to_eof() -> None:
    """The final section ends at the end of the file, outer blanks trimmed."""
    assert release_info.find_section(_NEWS, "1.2.2") == (
        "",
        "- Oldest, running to the end of the file",
    )


@pytest.mark.parametrize("version", ["1.2.1", "1.2.30", "1.2"])
def test_version_must_match_exactly(version: str) -> None:
    """A prefix or extension of a real version finds nothing."""
    assert release_info.find_section(_NEWS, version) is None


def test_exact_match_ignores_longer_versions() -> None:
    """1.2.3 does not pick up 1.2.3a1, and 1.2.1 would not pick up 1.2.10."""
    section = release_info.find_section(_NEWS, "1.2.3a1")
    assert section == ("", "- Alpha")
    assert release_info.find_section(_NEWS, "1.2.1") is None


def test_leading_v_in_expected_version() -> None:
    """--version accepts a leading v."""
    info = release_info.build_info(_pyproject("1.2.3"), _NEWS, "v1.2.3")
    assert info.version == "1.2.3"


def test_expected_version_mismatch() -> None:
    """A positional VERSION that disagrees with pyproject.toml is an error."""
    with pytest.raises(ReleaseInfoError, match=r"says 1\.2\.3, not 1\.2\.4"):
        release_info.build_info(_pyproject("1.2.3"), _NEWS, "1.2.4")


def test_target_version_is_not_the_version() -> None:
    """Only a line that is exactly version = "..." counts."""
    assert release_info.read_version(_pyproject("1.2.3")) == "1.2.3"
    with pytest.raises(ReleaseInfoError):
        release_info.read_version('target-version = "py312"\n')


@pytest.mark.parametrize(
    ("version", "final"),
    [("2.4.2", True), ("2.4.10", True), ("2.4.3a0", False), ("2.4", False)],
)
def test_final_regex(version: str, *, final: bool) -> None:
    """Only X.Y.Z is final, matching ci.yml's rule."""
    assert release_info.is_final(version) is final


# ---------------------------------------------------------------------------
# Errors and the alpha fallback
# ---------------------------------------------------------------------------


def test_duplicate_header_is_an_error() -> None:
    """Two sections for one version is ambiguous."""
    news = "## v1.0.0\n\n- one\n\n## v1.0.0 - Again\n\n- two\n"
    with pytest.raises(ReleaseInfoError, match="2 sections"):
        release_info.build_info(_pyproject("1.0.0"), news)


def test_missing_section_final_is_an_error() -> None:
    """A final version must have its own NEWS section."""
    with pytest.raises(ReleaseInfoError, match=r"'## v1\.2\.4' section"):
        release_info.build_info(_pyproject("1.2.4"), _NEWS)


def test_missing_section_alpha_falls_back() -> None:
    """An alpha without a section gets generic notes."""
    info = release_info.build_info(_pyproject("1.2.4a0"), _NEWS)
    assert not info.final
    assert info.title == "v1.2.4a0"
    assert info.notes == "Pre-release v1.2.4a0\n"


def test_empty_body_final_is_an_error() -> None:
    """A final section with only blank lines is an error."""
    news = "## v1.0.0\n\n\n## v0.9.0\n\n- old\n"
    with pytest.raises(ReleaseInfoError, match="non-empty"):
        release_info.build_info(_pyproject("1.0.0"), news)


# ---------------------------------------------------------------------------
# is-latest
# ---------------------------------------------------------------------------

_LS_REMOTE = [
    "aaa\trefs/tags/v2.4.9\n",
    "bbb\trefs/tags/v2.4.10a0\n",
    "ccc\trefs/tags/v2.3.3\n",
    "ddd\trefs/tags/not-a-version\n",
]


def test_is_latest_numeric_not_lexical() -> None:
    """2.4.10 beats 2.4.9."""
    assert release_info.is_latest("2.4.10", _LS_REMOTE)


def test_is_latest_ignores_alphas() -> None:
    """An alpha tag never outranks a final release."""
    assert release_info.is_latest("v2.4.9", _LS_REMOTE)


def test_is_latest_older_hotfix() -> None:
    """A hotfix on an older line is not latest."""
    assert not release_info.is_latest("2.3.4", _LS_REMOTE)


def test_is_latest_alpha_never_latest() -> None:
    """An alpha is never latest."""
    assert not release_info.is_latest("2.5.0a0", _LS_REMOTE)


def test_is_latest_no_tags() -> None:
    """The first release is latest."""
    assert release_info.is_latest("0.1.0", [])


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def test_cli_info_writes_outputs(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Info prints the facts, appends them to GITHUB_OUTPUT and writes notes."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(_pyproject("1.2.3"))
    news = tmp_path / "NEWS.md"
    news.write_text(_NEWS)
    notes = tmp_path / "notes.md"
    output = tmp_path / "output"
    output.write_text("earlier=kept\n")
    argv = ["info", "--pyproject", str(pyproject), "--news", str(news)]
    argv += ["--notes-file", str(notes), "--github-output", str(output)]

    assert release_info.main(argv) == 0

    facts = "version=1.2.3\ntag=v1.2.3\nfinal=true\ntitle=v1.2.3 - Sub & Title\n"
    assert capsys.readouterr().out == facts
    assert output.read_text() == "earlier=kept\n" + facts
    assert notes.read_text().startswith("- Features\n    - Nested bullet")


def test_cli_error_annotation(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Content errors exit 2 with a GitHub error annotation under Actions."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(_pyproject("1.2.4"))
    news = tmp_path / "NEWS.md"
    news.write_text(_NEWS)
    argv = ["info", "--pyproject", str(pyproject), "--news", str(news)]
    argv += ["--notes-file", str(tmp_path / "notes.md")]

    assert release_info.main(argv) == release_info.EXIT_CONTENT_ERROR
    assert capsys.readouterr().err.startswith("::error::NEWS.md needs")


def test_cli_is_latest(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """is-latest reads ls-remote lines from stdin."""
    monkeypatch.setattr(sys, "stdin", iter(_LS_REMOTE))
    assert release_info.main(["is-latest", "--version", "2.4.9"]) == 0
    assert capsys.readouterr().out == "true\n"


# ---------------------------------------------------------------------------
# Golden tests on the real NEWS.md
# ---------------------------------------------------------------------------

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

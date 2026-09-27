"""
bin/release-tag.sh against a throwaway origin.

Each test builds a bare origin whose main holds a squash-style release
commit with the same tree as a commit on develop, the way a develop -> main
PR lands. A fake ``gh`` on PATH logs every call and answers
``gh release view`` from a state file, so nothing reaches GitHub.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "bin" / "release-tag.sh"
# RELEASE_TAG_TEST_BASH=/bin/bash runs the suite under macOS's bash 3.2.
_BASH = os.environ.get("RELEASE_TAG_TEST_BASH") or shutil.which("bash") or ""
_GIT = shutil.which("git") or ""

pytestmark = pytest.mark.skipif(not (_BASH and _GIT), reason="needs bash and git")

_MERGE_MSG = "Merge branch 'main' into develop"
_TAG = "v1.2.3"
_NEWS_122 = "## v1.2.2\n\n- Old\n"
_NEWS_123 = "## v1.2.3 - Sub\n\n- New\n"
_STRIPPED_ENV_PREFIXES = ("GH_", "GIT_", "GITHUB_", "RELEASE_")
# A startup file named by these could reset PATH and hide the fake gh.
_STRIPPED_ENV_KEYS = frozenset(("BASH_ENV", "CDPATH", "ENV"))
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Release Test",
    "GIT_AUTHOR_EMAIL": "release@example.com",
    "GIT_COMMITTER_NAME": "Release Test",
    "GIT_COMMITTER_EMAIL": "release@example.com",
    # Keep the developer's own git config (signing, hooks, aliases) out.
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

_FAKE_GH = """#!{python}
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
entry = {{"argv": args}}
state_file = Path(os.environ["FAKE_GH_STATE"])
state = state_file.read_text().strip() if state_file.exists() else "missing"
if args[:2] == ["release", "view"]:
    if state == "missing":
        sys.stderr.write("release not found\\n")
        code = 1
    else:
        print("true" if state == "draft" else "false")
        code = 0
elif args[:2] == ["release", "create"]:
    entry["notes"] = Path(args[args.index("--notes-file") + 1]).read_text()
    state_file.write_text("published")
    code = 0
else:
    code = 2
with Path(os.environ["FAKE_GH_LOG"]).open("a") as log:
    log.write(json.dumps(entry) + "\\n")
sys.exit(code)
"""


def _base_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_STRIPPED_ENV_PREFIXES) and key not in _STRIPPED_ENV_KEYS
    }
    env.update(_GIT_ENV)
    return env


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603
        [_GIT, *args],
        cwd=cwd,
        env=_base_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _pyproject(version: str) -> str:
    return f'[project]\nname = "demo"\nversion = "{version}"\n'


def _news(*sections: str) -> str:
    return "# News\n\n" + "\n".join(sections)


def _commit(repo: Path, message: str, files: dict[str, str]) -> str:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@dataclass
class Release:
    """A bare origin, a seed repo that writes to it, and a caller's clone."""

    tmp: Path
    origin: Path
    seed: Path
    clone: Path
    base: str
    develop: str
    main: str

    # -- building scenarios -------------------------------------------------

    def commit_on(self, branch: str, files: dict[str, str], message: str) -> str:
        """Commit on a branch in the seed repo and push it to origin."""
        _git(self.seed, "switch", "-q", branch)
        sha = _commit(self.seed, message, files)
        _git(self.seed, "push", "-q", "origin", branch)
        return sha

    def push_tag(self, tag: str, sha: str) -> None:
        """Put a lightweight tag straight into origin."""
        _git(self.origin, "update-ref", f"refs/tags/{tag}", sha)

    def set_gh_state(self, state: str) -> None:
        """Set what the fake gh reports for release view."""
        (self.tmp / "gh-state").write_text(state)

    # -- running ------------------------------------------------------------

    def run(
        self,
        *args: str,
        sha: str | None,
        actions: bool = True,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the script from the clone; sha=None is a local run."""
        # A CI checkout has every commit; fetch what the scenario pushed.
        _git(self.clone, "fetch", "-q", "--no-tags", "origin")
        env = _base_env()
        env.update(
            PATH=f"{self.tmp / 'fakebin'}{os.pathsep}{env.get('PATH', '')}",
            TMPDIR=str(self.tmp / "script-tmp"),
            GITHUB_STEP_SUMMARY=str(self.tmp / "summary.md"),
            FAKE_GH_LOG=str(self.tmp / "gh-log.jsonl"),
            FAKE_GH_STATE=str(self.tmp / "gh-state"),
        )
        env.update(extra_env or {})
        if actions:
            env["GITHUB_ACTIONS"] = "true"
        if sha:
            env["RELEASE_SHA"] = sha
        result = subprocess.run(  # noqa: S603
            [_BASH, str(_SCRIPT), *args],
            cwd=self.clone,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self._assert_cleaned_up()
        return result

    def _assert_cleaned_up(self) -> None:
        leftovers = list((self.tmp / "script-tmp").iterdir())
        assert not leftovers, f"temp files left behind: {leftovers}"
        worktrees = _git(self.clone, "worktree", "list", "--porcelain")
        assert worktrees.count("worktree ") == 1, worktrees

    # -- inspecting ---------------------------------------------------------

    def remote_ref(self, ref: str) -> str:
        """Return the sha of a ref in origin, or '' when absent."""
        return _git(self.origin, "for-each-ref", "--format=%(objectname)", ref)

    def remote_refs(self) -> str:
        """Return every ref in origin, for before/after comparisons."""
        return _git(self.origin, "for-each-ref")

    def gh_calls(self) -> list[dict]:
        """Return every fake gh call, oldest first."""
        log = self.tmp / "gh-log.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def creates(self) -> list[dict]:
        """Return only the gh release create calls."""
        return [
            call
            for call in self.gh_calls()
            if call["argv"][:2] == ["release", "create"]
        ]

    def tree(self, rev: str) -> str:
        """Return the tree of a commit in origin."""
        return _git(self.origin, "rev-parse", f"{rev}^{{tree}}")

    def show(self, rev: str, path: str) -> str:
        """Return a file's contents at a commit in origin."""
        return _git(self.origin, "show", f"{rev}:{path}")

    def develop_merge(self, *parents: str) -> str:
        """Check origin's develop is the merge-back of these parents; return it."""
        merge = self.remote_ref("refs/heads/develop")
        rev_list = _git(self.origin, "rev-list", "--parents", "-n", "1", merge)
        assert rev_list.split()[1:] == list(parents)
        assert _git(self.origin, "log", "-1", "--format=%B", merge) == _MERGE_MSG
        return merge


def _make_fakebin(fakebin: Path) -> None:
    fakebin.mkdir()
    gh = fakebin / "gh"
    gh.write_text(_FAKE_GH.format(python=sys.executable))
    gh.chmod(0o755)
    # The script runs python3 bin/release_info.py; use this interpreter.
    (fakebin / "python3").symlink_to(sys.executable)


@pytest.fixture
def release(tmp_path: Path) -> Release:
    """Origin with v1.2.2 on both branches, then a v1.2.3 squash on main."""
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    clone = tmp_path / "clone"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _git(seed, "remote", "add", "origin", str(origin))
    base = _commit(
        seed,
        "v1.2.2",
        {
            "pyproject.toml": _pyproject("1.2.2"),
            "NEWS.md": _news(_NEWS_122),
            "app.txt": "one\n",
        },
    )
    _git(seed, "switch", "-q", "-c", "develop")
    develop = _commit(
        seed,
        "Release 1.2.3",
        {
            "pyproject.toml": _pyproject("1.2.3"),
            "NEWS.md": _news(_NEWS_123, _NEWS_122),
            "app.txt": "two\n",
        },
    )
    # The squash merge: develop's tree, main's parent.
    tree = _git(seed, "rev-parse", "develop^{tree}")
    main = _git(seed, "commit-tree", tree, "-p", base, "-m", "v1.2.3 (#1)")
    _git(seed, "branch", "-f", "main", main)
    _git(seed, "push", "-q", "origin", "main", "develop")
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _make_fakebin(tmp_path / "fakebin")
    (tmp_path / "script-tmp").mkdir()
    return Release(tmp_path, origin, seed, clone, base, develop, main)


# ---------------------------------------------------------------------------
# 1-3: the happy path, a re-run and a clash
# ---------------------------------------------------------------------------


def _assert_create(create: dict, title: str, flags: list[str], notes: str) -> None:
    argv = create["argv"]
    assert argv[:4] == ["release", "create", argv[2], "--verify-tag"]
    assert argv[argv.index("--title") + 1] == title
    assert argv[-len(flags) :] == flags
    assert create["notes"] == notes


def test_fresh_run(release: Release) -> None:
    """Tag, release and an -s ours merge that keeps develop's tree."""
    result = release.run(sha=release.main)
    assert result.returncode == 0, result.stderr

    assert release.remote_ref(f"refs/tags/{_TAG}") == release.main
    assert _git(release.origin, "cat-file", "-t", _TAG) == "commit"
    (create,) = release.creates()
    assert create["argv"][2] == _TAG
    _assert_create(create, "v1.2.3 - Sub", ["--latest"], "- New\n")
    merge = release.develop_merge(release.develop, release.main)
    assert release.tree(merge) == release.tree(release.develop)
    assert "Merged" in (release.tmp / "summary.md").read_text()


def test_rerun_is_a_noop(release: Release) -> None:
    """A second full run skips every step."""
    assert release.run(sha=release.main).returncode == 0
    refs = release.remote_refs()

    result = release.run(sha=release.main)

    assert result.returncode == 0, result.stderr
    assert release.remote_refs() == refs
    assert len(release.creates()) == 1
    assert "tag: v1.2.3 already at" in result.stdout
    assert "already exists" in result.stdout
    assert "develop already contains" in result.stdout


def test_tag_at_another_sha(release: Release) -> None:
    """A version already tagged elsewhere fails before anything is written."""
    release.push_tag(_TAG, release.base)
    refs = release.remote_refs()

    result = release.run(sha=release.main)

    assert result.returncode == 1
    assert f"::error::{_TAG} already released at {release.base[:7]}" in result.stderr
    assert release.remote_refs() == refs
    assert not release.creates()


# ---------------------------------------------------------------------------
# 4-5, 11-12: merge-back paths
# ---------------------------------------------------------------------------


def test_normal_path_merge(release: Release) -> None:
    """A main-only commit (an admin fix push) gets a real merge."""
    fix = release.commit_on("main", {"hotfix.txt": "fix\n"}, "fix version")

    result = release.run(sha=fix)

    assert result.returncode == 0, result.stderr
    assert "merging normally" in result.stdout
    merge = release.develop_merge(release.develop, fix)
    assert release.show(merge, "hotfix.txt") == "fix"
    assert release.show(merge, "app.txt") == "two"


def test_conflict_leaves_develop_alone(release: Release) -> None:
    """A real conflict fails loudly, names the file and pushes nothing."""
    moved = release.commit_on("develop", {"app.txt": "three\n"}, "develop moves on")
    fix = release.commit_on("main", {"app.txt": "hotfix\n"}, "hotfix on main")

    result = release.run(sha=fix)

    assert result.returncode == 1
    assert "conflicts in: app.txt" in result.stderr
    assert release.remote_ref("refs/heads/develop") == moved


def test_fast_path_keeps_a_later_develop_revert(release: Release) -> None:
    """-s ours keeps develop's tree, including a revert made after the PR."""
    revert = release.commit_on("develop", {"app.txt": "one\n"}, "Revert app change")

    result = release.run(sha=release.main)

    assert result.returncode == 0, result.stderr
    merge = release.develop_merge(revert, release.main)
    assert release.tree(merge) == release.tree(revert)
    assert release.show(merge, "app.txt") == "one"


def test_normal_path_workflow_warning(release: Release) -> None:
    """A merge that changes develop's workflows warns before the push."""
    wf = ".github/workflows/x.yml"
    fix = release.commit_on("main", {wf: "name: x\n"}, "workflow hotfix")

    result = release.run(sha=fix)

    assert result.returncode == 0, result.stderr
    assert f"::warning::the merge changes develop's workflow files ({wf})" in (
        result.stderr
    )


# Pushes a racing commit to develop just before the script's first develop push.
_RACING_GIT = """#!/usr/bin/env bash
if [[ "$*" == *HEAD:refs/heads/develop* && ! -e "$RACE_DONE" ]]; then
  touch "$RACE_DONE"
  "$REAL_GIT" -C "$RACE_SEED" push -q origin "$RACE_SHA:refs/heads/develop"
fi
exec "$REAL_GIT" "$@"
"""


def test_develop_moving_during_the_push_is_retried(release: Release) -> None:
    """A develop push rejected because develop moved is merged and pushed again."""
    _git(release.seed, "switch", "-q", "develop")
    racer = _commit(release.seed, "Racing develop commit", {"race.txt": "race\n"})
    wrapper = release.tmp / "fakebin" / "git"
    wrapper.write_text(_RACING_GIT)
    wrapper.chmod(0o755)
    race_env = {
        "REAL_GIT": _GIT,
        "RACE_DONE": str(release.tmp / "race-done"),
        "RACE_SEED": str(release.seed),
        "RACE_SHA": racer,
    }

    result = release.run(sha=release.main, extra_env=race_env)

    assert result.returncode == 0, result.stderr
    assert "retrying (1/3)" in result.stdout
    release.develop_merge(racer, release.main)


# ---------------------------------------------------------------------------
# 6-8: GitHub Release flags
# ---------------------------------------------------------------------------


def test_alpha_is_a_prerelease(release: Release) -> None:
    """An alpha needs no NEWS section and is never latest."""
    alpha = release.commit_on("main", {"pyproject.toml": _pyproject("1.2.4a0")}, "a0")

    assert release.run("tag", sha=alpha).returncode == 0
    result = release.run("publish", sha=alpha)

    assert result.returncode == 0, result.stderr
    assert release.remote_ref("refs/tags/v1.2.4a0") == alpha
    (create,) = release.creates()
    flags = ["--prerelease", "--latest=false"]
    _assert_create(create, "v1.2.4a0", flags, "Pre-release v1.2.4a0\n")


def test_older_hotfix_is_not_latest(release: Release) -> None:
    """A final release older than the newest final tag is not latest."""
    release.push_tag("v2.0.0", release.base)

    result = release.run("publish", sha=release.main)

    assert result.returncode == 0, result.stderr
    (create,) = release.creates()
    assert create["argv"][-1] == "--latest=false"
    assert "--prerelease" not in create["argv"]


def test_existing_draft_is_left_alone(release: Release) -> None:
    """A draft someone made by hand wins; the job warns and moves on."""
    release.set_gh_state("draft")

    result = release.run(sha=release.main)

    assert result.returncode == 0, result.stderr
    assert not release.creates()
    assert "::warning::publish: GitHub Release v1.2.3 exists as a draft" in (
        result.stderr
    )


# ---------------------------------------------------------------------------
# 9-10: dry run and a local run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "extra"),
    [(("--dry-run",), {}), ((), {"RELEASE_DRY_RUN": "1"})],
    ids=["flag", "env"],
)
def test_dry_run_writes_nothing(
    release: Release, args: tuple[str, ...], extra: dict[str, str]
) -> None:
    """--dry-run prints every remote write and performs none."""
    refs = release.remote_refs()

    result = release.run(*args, sha=release.main, extra_env=extra)

    assert result.returncode == 0, result.stderr
    assert release.remote_refs() == refs
    assert not release.creates()
    assert f"+ git push origin {release.main}:refs/tags/{_TAG}" in result.stdout
    assert "+ gh release create v1.2.3 --verify-tag" in result.stdout
    assert "+ git -C" in result.stdout
    assert "HEAD:refs/heads/develop" in result.stdout


def _checkout_state(repo: Path) -> tuple[str, ...]:
    return (
        _git(repo, "rev-parse", "HEAD"),
        _git(repo, "branch", "--show-current"),
        _git(repo, "status", "--porcelain"),
        _git(repo, "tag", "--list"),
        _git(repo, "stash", "list"),
    )


def test_local_run_leaves_the_checkout_alone(release: Release) -> None:
    """Without RELEASE_SHA it releases origin/main without touching the clone."""
    _git(release.clone, "switch", "-q", "-c", "feature", "origin/develop")
    _commit(release.clone, "local work", {"local.txt": "mine\n"})
    (release.clone / "app.txt").write_text("uncommitted\n")
    (release.clone / "untracked.txt").write_text("untracked\n")
    before = _checkout_state(release.clone)

    result = release.run(sha=None, actions=False)

    assert result.returncode == 0, result.stderr
    assert _checkout_state(release.clone) == before
    assert release.remote_ref(f"refs/tags/{_TAG}") == release.main
    release.develop_merge(release.develop, release.main)


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def test_preflight_missing_news_section(release: Release) -> None:
    """A final version without its NEWS section fails the preflight."""
    bump = release.commit_on("main", {"pyproject.toml": _pyproject("1.2.4")}, "bump")
    refs = release.remote_refs()

    result = release.run("preflight", sha=bump)

    assert result.returncode != 0
    assert "::error::NEWS.md needs a non-empty '## v1.2.4' section" in result.stderr
    assert release.remote_refs() == refs


@pytest.mark.parametrize(("version", "code"), [("v1.2.3", 0), ("1.2.4", 2)])
def test_preflight_version_assertion(release: Release, version: str, code: int) -> None:
    """A positional VERSION only asserts what pyproject.toml says."""
    result = release.run("preflight", version, sha=release.main)

    assert result.returncode == code, result.stderr
    assert not release.gh_calls()


# ---------------------------------------------------------------------------
# 13: static checks, the only shell lint CI runs
# ---------------------------------------------------------------------------


def test_script_parses() -> None:
    """Check that bash -n accepts the script."""
    subprocess.run([_BASH, "-n", str(_SCRIPT)], check=True)  # noqa: S603


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="needs shellcheck")
def test_script_passes_shellcheck() -> None:
    """Shellcheck is clean."""
    shellcheck = shutil.which("shellcheck") or ""
    subprocess.run(  # noqa: S603
        [shellcheck, "--external-sources", str(_SCRIPT)],
        check=True,
        cwd=_ROOT,
    )

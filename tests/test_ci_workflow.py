"""
Invariants of codex's CI in .github/workflows/ci.yml.

ci.yml composes devenv's CI building blocks: devenv-check (the gate, one
codex-ci image, the fail-fast check matrix and the required check
"CI / Lint, Test & Build Dist") and devenv-release, with codex's own image,
manifest, PyPI and Docker Hub jobs between them. devenv tests the blocks
themselves; these tests pin how codex wires them. CI never runs actionlint,
so these are the only workflow checks CI enforces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

_WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
_CALL_CHECK = "./.github/workflows/devenv-check.yml"
_CALL_RELEASE = "./.github/workflows/devenv-release.yml"
_CALL_PYPI = "./.github/actions/devenv-pypi"
_MATRIX = (
    ("Lint", "lint"),
    ("Test Frontend", "test-frontend"),
    ("Test Python", "django-check test-python"),
    ("Build Dist", "build-choices build-frontend collectstatic build-only"),
)
_DEPLOY_JOBS = ("build", "deploy", "deploy-hub")
_LATER_JOBS = [*_DEPLOY_JOBS, "release"]
_EVENT_TESTS = ("github.event_name", "github.ref", "base_ref", "head_ref")


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    """Return the workflow's jobs by id."""
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else needs


def _ancestors(jobs: dict[str, Any], job_id: str) -> set[str]:
    found: set[str] = set()
    todo = _needs(jobs[job_id])
    while todo:
        need = todo.pop()
        if need not in found:
            found.add(need)
            todo.extend(_needs(jobs[need]))
    return found


def test_ci_is_devenv_check_with_the_codex_ci_image(jobs: dict[str, Any]) -> None:
    """The required check is "CI / Lint, Test & Build Dist", so ci keeps its name."""
    ci = jobs["ci"]
    assert ci["uses"] == _CALL_CHECK
    assert ci["name"] == "CI"
    assert ci["with"]["ci-target"] == "codex-ci"
    assert ci["permissions"] == {
        "contents": "read",
        "actions": "read",
        "packages": "write",
        "checks": "write",
    }


def test_check_matrix(jobs: dict[str, Any]) -> None:
    """Four combos; Test Python publishes junit and Build Dist the dist."""
    matrix = json.loads(jobs["ci"]["with"]["matrix"])
    assert tuple((combo["name"], combo["make"]) for combo in matrix) == _MATRIX
    assert [combo["name"] for combo in matrix if combo.get("junit")] == ["Test Python"]
    assert [combo["name"] for combo in matrix if combo.get("dist")] == ["Build Dist"]


@pytest.mark.parametrize("job_id", _LATER_JOBS)
def test_later_jobs_need_explicit_success(jobs: dict[str, Any], job_id: str) -> None:
    """!cancelled() plus explicit results: a cancelled ancestor never passes."""
    job = jobs[job_id]
    condition = job["if"]
    assert "!cancelled()" in condition
    for need in [need for need in _needs(job) if need != "ci"] or ["ci"]:
        assert f"needs.{need}.result ==" in condition, need


@pytest.mark.parametrize("job_id", _LATER_JOBS)
def test_triggers_come_from_ci(jobs: dict[str, Any], job_id: str) -> None:
    """Later jobs read ci's outputs and never test the event themselves."""
    job = jobs[job_id]
    assert "ci" in _needs(job)
    for event_test in _EVENT_TESTS:
        assert event_test not in job["if"], event_test


def test_images_build_only_on_deploy(jobs: dict[str, Any]) -> None:
    """Main pushes and pre-release PRs build images, from ci's version."""
    build = jobs["build"]
    assert "needs.ci.outputs.deploy == 'true'" in build["if"]
    assert build["env"]["CODEX_VERSION"] == "${{ needs.ci.outputs.version }}"


def test_versions_come_from_ci(jobs: dict[str, Any]) -> None:
    """No deploy job reads the version from pyproject.toml itself."""
    for job_id in _DEPLOY_JOBS:
        for step in jobs[job_id]["steps"]:
            run = step.get("run", "")
            assert "pyproject.toml" not in run, (job_id, step["name"])
            assert "uv version" not in run, (job_id, step["name"])


def test_pypi_publishes_after_the_manifest(jobs: dict[str, Any]) -> None:
    """Images first: a PyPI version can never be replaced."""
    names = [step.get("name") for step in jobs["deploy"]["steps"]]
    (pypi,) = [
        step for step in jobs["deploy"]["steps"] if step.get("uses") == _CALL_PYPI
    ]
    assert names.index("Create and push manifest") < names.index(pypi["name"])
    assert pypi["with"]["download"] == "false"


def test_pypi_job_can_get_an_identity_token(jobs: dict[str, Any]) -> None:
    """PyPI trusted publishing fails at the token exchange without id-token: write."""
    assert jobs["deploy"]["permissions"]["id-token"] == "write"


def test_docker_hub_gets_final_releases_only(jobs: dict[str, Any]) -> None:
    """Alphas never reach Docker Hub."""
    assert "needs.ci.outputs.final == 'true'" in jobs["deploy-hub"]["if"]


def test_release_runs_last_on_main_pushes(jobs: dict[str, Any]) -> None:
    """The release waits for every deploy job and runs only on outputs.release."""
    release = jobs["release"]
    assert release["uses"] == _CALL_RELEASE
    assert "needs.ci.outputs.release == 'true'" in release["if"]
    assert release["permissions"] == {"contents": "write"}
    assert set(_DEPLOY_JOBS) <= _ancestors(jobs, "release")

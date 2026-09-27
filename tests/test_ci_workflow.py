"""
Invariants of the CI job graph in .github/workflows/ci.yml.

"Lint, Test & Build Dist" is the required check on main, so it must keep its
name and fail closed. The check matrix must stop at the first failure, and
nothing downstream may run unless everything it depends on succeeded. CI
never runs actionlint, so these are the only workflow checks CI enforces.

What GitHub reports as ``needs.check.result`` when one matrix combo failed
and fail-fast cancelled the rest is recorded by the graph simulation
(tasks/ci-job-split.md §5 case g). The aggregator accepts only "success", so
any other value fails closed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

_WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
_REQUIRED_CHECK = "Lint, Test & Build Dist"
_CHECK_NAMES = frozenset(("Lint", "Test Frontend", "Test Python", "Build Dist"))
_DOWNSTREAM = ("build", "deploy", "deploy-hub", "release")
_DIST_ARTIFACT = "python-dist"


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    """Return the parsed workflow."""
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the workflow's jobs by id."""
    return workflow["jobs"]


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return job.get("steps", [])


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else needs


def test_workflow_name_is_ci(workflow: dict[str, Any]) -> None:
    """bin/ci-download-dist-if-identical.sh looks up earlier runs named CI."""
    assert workflow["name"] == "CI"


def test_required_check_aggregates_every_container_job(jobs: dict[str, Any]) -> None:
    """The required check runs always() and needs every job that runs tests."""
    (aggregator,) = (job for job in jobs.values() if job.get("name") == _REQUIRED_CHECK)
    assert "always()" in aggregator["if"]
    container_jobs = {
        job_id
        for job_id, job in jobs.items()
        if any("docker exec" in step.get("run", "") for step in _steps(job))
    }
    assert "check" in container_jobs
    assert container_jobs <= set(_needs(aggregator))


def test_check_matrix_fails_fast(jobs: dict[str, Any]) -> None:
    """The first failing combo must cancel the rest (decided 2026-09-23)."""
    check = jobs["check"]
    assert check["strategy"]["fail-fast"] is True
    assert "continue-on-error" not in check
    assert all("continue-on-error" not in step for step in _steps(check))
    assert check["name"] == "${{ matrix.name }}"


def test_check_matrix_combos(jobs: dict[str, Any]) -> None:
    """Four named combos, and only one writes the registry cache."""
    include = jobs["check"]["strategy"]["matrix"]["include"]
    assert {combo["name"] for combo in include} == _CHECK_NAMES
    assert len(include) == len(_CHECK_NAMES)
    assert [combo["task"] for combo in include if combo["write-cache"] is True] == [
        "lint"
    ]


@pytest.mark.parametrize("job_id", _DOWNSTREAM)
def test_downstream_jobs_need_explicit_success(
    jobs: dict[str, Any], job_id: str
) -> None:
    """!cancelled() plus explicit results: a cancelled ancestor never passes."""
    condition = jobs[job_id]["if"]
    assert "!cancelled()" in condition
    assert ".result == 'success'" in condition


def test_python_dist_has_two_guarded_producers(jobs: dict[str, Any]) -> None:
    """Only the gate (on reuse) and the Build Dist combo upload python-dist."""
    producers = {
        job_id: step.get("if", "")
        for job_id, job in jobs.items()
        for step in _steps(job)
        if "upload-artifact" in step.get("uses", "")
        and step.get("with", {}).get("name") == _DIST_ARTIFACT
    }
    assert set(producers) == {"gate", "check"}
    assert "dist_found == 'true'" in producers["gate"]
    assert "matrix.task == 'dist'" in producers["check"]


def test_release_preflight_runs_once_in_the_gate(jobs: dict[str, Any]) -> None:
    """The preflight fails the gate, which fails the required check."""
    preflights = [
        (job_id, step)
        for job_id, job in jobs.items()
        for step in _steps(job)
        if step.get("name") == "Release Preflight"
    ]
    assert [job_id for job_id, _ in preflights] == ["gate"]
    assert preflights[0][1]["run"] == "bin/release-tag.sh preflight"
    checkout = _steps(jobs["gate"])[0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert "if" not in checkout


def test_release_job_runs_only_after_a_main_deploy(jobs: dict[str, Any]) -> None:
    """The release job is the last job and only runs for a push to main."""
    release = jobs["release"]
    assert set(_needs(release)) == {"deploy", "deploy-hub"}
    assert "github.ref == 'refs/heads/main'" in release["if"]
    assert release["permissions"] == {"contents": "write"}

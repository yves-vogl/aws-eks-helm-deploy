"""Structural tests for scripts/benchmark-cold-start.sh and the benchmark-cold-start
job in .github/workflows/release.yml.

Phase 6 / IMAGE-06 / CI-04. Asserts:
- scripts/benchmark-cold-start.sh exists and is executable
- release.yml has a benchmark-cold-start job with correct structure
- benchmark job permissions are minimal (no id-token:write / attestations:write)
- bitbucket-pipelines.yml has no docker build/push or Docker Hub credential references
"""

from __future__ import annotations

import pathlib
import stat
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCHMARK_SCRIPT = REPO_ROOT / "scripts" / "benchmark-cold-start.sh"
RELEASE_YML_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
BITBUCKET_YML_PATH = REPO_ROOT / "bitbucket-pipelines.yml"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def release_workflow() -> dict[str, Any]:
    """Load release.yml once and share across all tests in this module."""
    return yaml.safe_load(RELEASE_YML_PATH.read_text())  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def bitbucket_pipeline() -> dict[str, Any]:
    """Load bitbucket-pipelines.yml once and share across all tests in this module."""
    return yaml.safe_load(BITBUCKET_YML_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# benchmark-cold-start.sh tests
# ---------------------------------------------------------------------------


def test_benchmark_script_exists() -> None:
    """scripts/benchmark-cold-start.sh must exist."""
    assert BENCHMARK_SCRIPT.exists(), (
        f"Missing: {BENCHMARK_SCRIPT}. Task 2 of plan 06-11 should have created it."
    )


def test_benchmark_script_is_executable() -> None:
    """scripts/benchmark-cold-start.sh must have the executable bit set."""
    mode = BENCHMARK_SCRIPT.stat().st_mode
    assert bool(mode & stat.S_IXUSR), (
        f"{BENCHMARK_SCRIPT} is not executable (mode={oct(mode)}). "
        "Run: git update-index --chmod=+x scripts/benchmark-cold-start.sh"
    )


def test_benchmark_script_has_target_ms() -> None:
    """Script must encode the IMAGE-06 10s documented target threshold."""
    content = BENCHMARK_SCRIPT.read_text()
    assert "TARGET_MS=10000" in content, (
        "scripts/benchmark-cold-start.sh must define TARGET_MS=10000 (IMAGE-06 target)."
    )


def test_benchmark_script_has_catastrophic_ms() -> None:
    """Script must encode the 30s catastrophic CI-fail threshold (RESEARCH A6)."""
    content = BENCHMARK_SCRIPT.read_text()
    assert "CATASTROPHIC_MS=30000" in content, (
        "scripts/benchmark-cold-start.sh must define CATASTROPHIC_MS=30000 "
        "(hard CI fail per RESEARCH A6)."
    )


def test_benchmark_script_prepulls_image() -> None:
    """Script must pre-pull the image to exclude network time (IMAGE-06 spec)."""
    content = BENCHMARK_SCRIPT.read_text()
    assert "docker pull" in content, (
        "scripts/benchmark-cold-start.sh must pre-pull the image before timing "
        "(IMAGE-06 spec: network time excluded)."
    )


# ---------------------------------------------------------------------------
# release.yml benchmark-cold-start job tests
# ---------------------------------------------------------------------------


def test_release_yml_has_benchmark_job(release_workflow: dict[str, Any]) -> None:
    """release.yml must have a benchmark-cold-start job."""
    jobs = release_workflow.get("jobs", {})
    assert "benchmark-cold-start" in jobs, (
        "release.yml is missing the 'benchmark-cold-start' job. "
        "Plan 06-11 should have appended it after sign-and-attest."
    )


def test_benchmark_job_needs_sign_and_attest(release_workflow: dict[str, Any]) -> None:
    """benchmark-cold-start must depend on sign-and-attest."""
    job = release_workflow["jobs"]["benchmark-cold-start"]
    needs = job.get("needs", [])
    # needs can be a list or a single string
    if isinstance(needs, str):
        needs = [needs]
    assert "sign-and-attest" in needs, (
        "benchmark-cold-start job must have 'needs: [sign-and-attest]' "
        "to run after the image is published."
    )


def test_benchmark_job_permissions_minimal(release_workflow: dict[str, Any]) -> None:
    """benchmark-cold-start must have minimal permissions: contents: read only."""
    job = release_workflow["jobs"]["benchmark-cold-start"]
    permissions = job.get("permissions", {})
    assert "id-token" not in permissions, (
        "benchmark-cold-start must NOT have id-token permission (no signing; read-only benchmark)."
    )
    assert "attestations" not in permissions, (
        "benchmark-cold-start must NOT have attestations permission "
        "(no signing; read-only benchmark)."
    )
    assert permissions.get("contents") == "read", (
        f"benchmark-cold-start permissions.contents should be 'read', got: "
        f"{permissions.get('contents')!r}"
    )


def test_benchmark_job_invokes_script(release_workflow: dict[str, Any]) -> None:
    """benchmark-cold-start job must invoke scripts/benchmark-cold-start.sh."""
    job = release_workflow["jobs"]["benchmark-cold-start"]
    steps = job.get("steps", [])
    script_invoked = any("benchmark-cold-start.sh" in str(step.get("run", "")) for step in steps)
    assert script_invoked, (
        "benchmark-cold-start job must invoke scripts/benchmark-cold-start.sh in a run step."
    )


def test_benchmark_job_uploads_artifact(release_workflow: dict[str, Any]) -> None:
    """benchmark-cold-start job must upload the JSON result as a workflow artifact."""
    job = release_workflow["jobs"]["benchmark-cold-start"]
    steps = job.get("steps", [])
    upload_step = next(
        (step for step in steps if "upload-artifact" in str(step.get("uses", ""))),
        None,
    )
    assert upload_step is not None, (
        "benchmark-cold-start job must have an upload-artifact step "
        "to persist the benchmark JSON for investigation."
    )


# ---------------------------------------------------------------------------
# bitbucket-pipelines.yml tests (CI-04)
# ---------------------------------------------------------------------------


def test_bitbucket_no_docker_build(bitbucket_pipeline: dict[str, Any]) -> None:
    """bitbucket-pipelines.yml must contain no 'docker build' references (CI-04)."""
    raw = BITBUCKET_YML_PATH.read_text()
    assert "docker build" not in raw, (
        "bitbucket-pipelines.yml must not contain 'docker build'. "
        "Image builds are handled by GitHub Actions."
    )


def test_bitbucket_no_docker_push(bitbucket_pipeline: dict[str, Any]) -> None:
    """bitbucket-pipelines.yml must contain no 'docker push' references (CI-04)."""
    raw = BITBUCKET_YML_PATH.read_text()
    assert "docker push" not in raw, (
        "bitbucket-pipelines.yml must not contain 'docker push'. "
        "Image publishing is handled by GitHub Actions."
    )


def test_bitbucket_no_dockerhub_credentials(bitbucket_pipeline: dict[str, Any]) -> None:
    """bitbucket-pipelines.yml must not reference Docker Hub credential env vars.

    CI-04 / T-06-11-01: long-lived Docker Hub credentials eliminated.
    """
    raw = BITBUCKET_YML_PATH.read_text()
    dockerhub_cred_markers = ["DOCKERHUB_USERNAME", "DOCKERHUB_PASSWORD", "DOCKERHUB_TOKEN"]
    for marker in dockerhub_cred_markers:
        assert marker not in raw, (
            f"bitbucket-pipelines.yml must not reference '{marker}'. "
            "Long-lived Docker Hub credentials have been eliminated (CI-04 / MIG-01)."
        )


def test_bitbucket_pipeline_is_yaml_valid(bitbucket_pipeline: dict[str, Any]) -> None:
    """bitbucket-pipelines.yml must be valid YAML (fixture parses it; checks it loaded)."""
    assert isinstance(bitbucket_pipeline, dict), (
        "bitbucket-pipelines.yml could not be parsed as a YAML mapping."
    )
    assert "pipelines" in bitbucket_pipeline, (
        "bitbucket-pipelines.yml must have a 'pipelines:' key."
    )

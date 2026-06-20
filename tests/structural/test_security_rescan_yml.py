"""Structural tests for .github/workflows/security-rescan.yml (Phase 6 / SEC-07).

Asserts: daily cron trigger, workflow_dispatch, no id-token:write, matrix over both
tags, SARIF upload step, issue-creator script invoked, Trivy action SHA-pinned,
bootstrap-graceful probe step, ubuntu-24.04 runner, minimal permissions block.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SECURITY_RESCAN_YML_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "security-rescan.yml"
)

# SHA from 06-RESEARCH.md "Action Digest Resolution" (verified via gh api 2026-06-20)
TRIVY_ACTION_SHA = "ed142fd0673e97e23eac54620cfb913e5ce36c25"  # v0.36.0
UPLOAD_SARIF_SHA = "dd903d2e4f5405488e5ef1422510ee31c8b32357"  # codeql-action v3

EXPECTED_CRON = "17 6 * * *"
EXPECTED_MATRIX_TAGS: frozenset[str] = frozenset({"latest", "2"})

# ---------------------------------------------------------------------------
# Module-level fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    """Load security-rescan.yml once and share across all tests in this module."""
    return yaml.safe_load(SECURITY_RESCAN_YML_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_on_block(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the ``on:`` trigger block, handling PyYAML's YAML-1.1 bool coercion.

    PyYAML may parse bare ``on:`` as the boolean ``True`` (YAML 1.1 compat).
    """
    if "on" in workflow:
        value = workflow["on"]
    else:
        raw: dict[Any, Any] = dict(workflow)
        value = None
        for key in raw:
            if key is True:
                value = raw[key]
                break
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {item: {} for item in value}
    if isinstance(value, str):
        return {value: {}}
    return {}


def _all_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten all steps from all jobs in the workflow into a single list."""
    steps: list[dict[str, Any]] = []
    jobs: dict[str, Any] = workflow.get("jobs", {})
    for job_def in jobs.values():
        for step in job_def.get("steps", []):
            steps.append(step)
    return steps


def _get_rescan_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of steps in the ``rescan`` job."""
    job: dict[str, Any] = workflow.get("jobs", {}).get("rescan", {})
    return list(job.get("steps", []))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_security_rescan_yml_exists() -> None:
    """security-rescan.yml must exist at the expected path."""
    assert SECURITY_RESCAN_YML_PATH.is_file(), (
        f"Expected {SECURITY_RESCAN_YML_PATH} to exist — Task 3 (06-07) creates it"
    )


def test_security_rescan_has_daily_cron(workflow: dict[str, Any]) -> None:
    """on.schedule must contain a daily cron entry (SEC-07)."""
    on_block = _get_on_block(workflow)
    schedule: list[dict[str, str]] = on_block.get("schedule", [])
    assert isinstance(schedule, list) and len(schedule) >= 1, (
        f"Expected 'schedule:' with at least one cron entry; got {schedule!r}"
    )
    cron_expressions = [entry.get("cron", "") for entry in schedule]
    assert EXPECTED_CRON in cron_expressions, (
        f"Expected cron '{EXPECTED_CRON}' in schedule; got {cron_expressions}"
    )


def test_security_rescan_has_workflow_dispatch(workflow: dict[str, Any]) -> None:
    """on.workflow_dispatch must be present for manual triggering."""
    on_block = _get_on_block(workflow)
    assert "workflow_dispatch" in on_block, (
        "Expected 'workflow_dispatch:' trigger in security-rescan.yml for manual runs"
    )


def test_security_rescan_no_id_token_write(workflow: dict[str, Any]) -> None:
    """No permissions block (workflow or job-level) may grant id-token: write (Pitfall #1).

    Scheduled workflows do NOT need OIDC tokens.
    """
    # Workflow-level
    wf_perms: Any = workflow.get("permissions", {})
    if isinstance(wf_perms, dict):
        assert wf_perms.get("id-token") != "write", (
            "Pitfall #1 violation: workflow-level permissions.id-token must not be 'write' "
            "in security-rescan.yml (cron/scheduled workflow)"
        )
    # Per-job level
    jobs: dict[str, Any] = workflow.get("jobs", {})
    for job_name, job_def in jobs.items():
        job_perms: Any = job_def.get("permissions", {})
        if isinstance(job_perms, dict):
            assert job_perms.get("id-token") != "write", (
                f"Pitfall #1 violation: job '{job_name}' permissions.id-token must not be "
                "'write' in security-rescan.yml"
            )


def test_security_rescan_permissions_minimal(workflow: dict[str, Any]) -> None:
    """Workflow-level permissions must include contents:read, security-events:write, issues:write.

    NO id-token present at all (Pitfall #1 guard).
    """
    perms: Any = workflow.get("permissions", {})
    assert isinstance(perms, dict), (
        f"Expected 'permissions:' to be a dict; got {type(perms).__name__}"
    )
    assert perms.get("contents") == "read", (
        f"Expected permissions.contents: read; got {perms.get('contents')!r}"
    )
    assert perms.get("security-events") == "write", (
        f"Expected permissions.security-events: write; got {perms.get('security-events')!r}"
    )
    assert perms.get("issues") == "write", (
        f"Expected permissions.issues: write; got {perms.get('issues')!r}"
    )
    assert "id-token" not in perms, (
        f"Pitfall #1 violation: permissions must NOT include 'id-token' in security-rescan.yml; "
        f"found permissions.id-token: {perms.get('id-token')!r}"
    )


def test_security_rescan_matrix_covers_latest_and_2(workflow: dict[str, Any]) -> None:
    """Matrix tag list must cover both 'latest' and '2' (SEC-07: scans both published tags)."""
    rescan_job: dict[str, Any] = workflow.get("jobs", {}).get("rescan", {})
    matrix: dict[str, Any] = rescan_job.get("strategy", {}).get("matrix", {})
    tags: list[Any] = matrix.get("tag", [])
    # Normalize to strings (YAML may parse "2" as int 2 if unquoted)
    tag_strings: frozenset[str] = frozenset(str(t) for t in tags)
    assert tag_strings >= EXPECTED_MATRIX_TAGS, (
        f"Matrix must include tags {EXPECTED_MATRIX_TAGS}; got {tag_strings}. "
        "SEC-07 requires scanning both :latest and :2 published image tags."
    )


def test_security_rescan_uploads_sarif(workflow: dict[str, Any]) -> None:
    """At least one step must use github/codeql-action/upload-sarif (SEC-07 Code Scanning)."""
    steps = _all_steps(workflow)
    upload_steps = [s for s in steps if "upload-sarif" in s.get("uses", "")]
    assert len(upload_steps) >= 1, (
        "No upload-sarif step found in security-rescan.yml. "
        "SEC-07 requires SARIF upload to GitHub Code Scanning via codeql-action/upload-sarif."
    )
    # Verify it is SHA-pinned to the expected digest
    for step in upload_steps:
        uses: str = step.get("uses", "")
        assert UPLOAD_SARIF_SHA in uses, (
            f"upload-sarif step must be pinned to SHA '{UPLOAD_SARIF_SHA}'; got {uses!r}"
        )


def test_security_rescan_invokes_issue_creator(workflow: dict[str, Any]) -> None:
    """At least one step must invoke scripts/rescan-issue-creator.py (SEC-07 dedup issues)."""
    steps = _all_steps(workflow)
    script_steps = [s for s in steps if "scripts/rescan-issue-creator.py" in s.get("run", "")]
    assert len(script_steps) >= 1, (
        "No step in security-rescan.yml invokes scripts/rescan-issue-creator.py. "
        "SEC-07 requires the dedup-aware issue creator to run after Trivy scan."
    )


def test_security_rescan_trivy_action_pinned(workflow: dict[str, Any]) -> None:
    """aquasecurity/trivy-action step must be pinned to the verified SHA (v0.36.0 per RESEARCH)."""
    steps = _all_steps(workflow)
    trivy_steps = [s for s in steps if "aquasecurity/trivy-action" in s.get("uses", "")]
    assert len(trivy_steps) >= 1, "No aquasecurity/trivy-action step found in security-rescan.yml"
    for step in trivy_steps:
        uses: str = step.get("uses", "")
        assert uses.endswith(f"@{TRIVY_ACTION_SHA}"), (
            f"trivy-action must be pinned to SHA '{TRIVY_ACTION_SHA}' (v0.36.0); got {uses!r}"
        )


def test_security_rescan_has_probe_step(workflow: dict[str, Any]) -> None:
    """A step with id: probe must exist (bootstrap-graceful guard — T-06-07-03).

    The probe step skips rescan if the image doesn't exist yet (pre-first-release).
    """
    steps = _get_rescan_steps(workflow)
    probe_step: dict[str, Any] | None = None
    for step in steps:
        if step.get("id") == "probe":
            probe_step = step
            break
    assert probe_step is not None, (
        "Bootstrap-graceful probe step (id: probe) not found in 'rescan' job. "
        "T-06-07-03: rescan must skip gracefully before first release (empty GHCR registry)."
    )
    probe_run: str = probe_step.get("run", "")
    assert "exists=true" in probe_run, (
        "Probe step must set 'exists=true' output when image manifest is found"
    )
    assert "exists=false" in probe_run, (
        "Probe step must set 'exists=false' output when image is absent (bootstrap case)"
    )


def test_security_rescan_runs_on_pinned_ubuntu(workflow: dict[str, Any]) -> None:
    """rescan job must run on ubuntu-24.04 (D4 — NOT ubuntu-latest)."""
    rescan_job: dict[str, Any] = workflow.get("jobs", {}).get("rescan", {})
    runs_on: Any = rescan_job.get("runs-on")
    assert runs_on == "ubuntu-24.04", (
        f"D4 violation: rescan job must use 'ubuntu-24.04' (pinned); got {runs_on!r}. "
        "Do not use 'ubuntu-latest' — the pinned label ensures reproducible runner versions."
    )

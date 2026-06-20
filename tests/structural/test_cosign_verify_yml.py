"""Structural tests for .github/workflows/cosign-verify.yml.

Phase 6 / SEC-01 / CONTEXT D7 / Pitfall #1. Asserts: pull_request trigger
(not pull_request_target), no id-token elevation, both SBOM attestations
verified, bootstrap-graceful probe step present.
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

COSIGN_VERIFY_YML_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "cosign-verify.yml"
)

# SHA from 06-RESEARCH.md "Action Digest Resolution" (verified via gh api 2026-06-20)
COSIGN_INSTALLER_SHA = "6f9f17788090df1f26f669e9d70d6ae9567deba6"  # v4.1.2

CERT_IDENTITY_REGEXP = "^https://github.com/yves-vogl/aws-eks-helm-deploy/"
CERT_OIDC_ISSUER = "https://token.actions.githubusercontent.com"

# ---------------------------------------------------------------------------
# Module-level fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    """Load cosign-verify.yml once and share across all tests in this module."""
    return yaml.safe_load(COSIGN_VERIFY_YML_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalize_on(on_value: dict[str, Any] | list[str] | str) -> dict[str, Any]:
    """Normalise the ``on:`` field to a uniform dict shape.

    PyYAML (YAML 1.1) may parse ``on:`` as the boolean ``True``. The value
    passed here is already the *value* of the key, so we handle:

    - ``dict``  — standard ``on: push: …`` YAML map
    - ``list``  — ``on: [push, pull_request]`` shorthand
    - ``str``   — ``on: push`` single-trigger shorthand
    """
    if isinstance(on_value, dict):
        return on_value
    if isinstance(on_value, list):
        return {item: {} for item in on_value}
    if isinstance(on_value, str):
        return {on_value: {}}
    return {}


def _get_on_block(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the ``on:`` trigger block, handling PyYAML's YAML-1.1 bool coercion."""
    if "on" in workflow:
        return _normalize_on(workflow["on"])
    raw: dict[Any, Any] = dict(workflow)
    for key in raw:
        if key is True:
            return _normalize_on(raw[key])
    return {}


def _get_verify_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of steps in the ``verify`` job."""
    job: dict[str, Any] = workflow.get("jobs", {}).get("verify", {})
    return list(job.get("steps", []))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cosign_verify_yml_exists() -> None:
    """cosign-verify.yml must exist at the expected path."""
    assert COSIGN_VERIFY_YML_PATH.is_file(), (
        f"Expected {COSIGN_VERIFY_YML_PATH} to exist — Task 1 (06-05) creates it"
    )


def test_cosign_verify_triggers_on_pull_request(workflow: dict[str, Any]) -> None:
    """cosign-verify.yml must trigger on pull_request events."""
    on_block = _get_on_block(workflow)
    assert "pull_request" in on_block, (
        f"Expected 'pull_request' trigger in cosign-verify.yml; got triggers: {list(on_block)}"
    )


def test_cosign_verify_does_not_use_pull_request_target(workflow: dict[str, Any]) -> None:
    """cosign-verify.yml must NOT use pull_request_target (Pitfall #1 — OIDC elevation risk)."""
    on_block = _get_on_block(workflow)
    assert "pull_request_target" not in on_block, (
        "Security violation (Pitfall #1): cosign-verify.yml must not use pull_request_target — "
        "that trigger runs in the context of the target repo and can expose OIDC tokens to "
        "untrusted PRs from forks."
    )


def test_cosign_verify_workflow_permissions_minimal(workflow: dict[str, Any]) -> None:
    """Workflow-level permissions must be exactly {'contents': 'read'} — least privilege."""
    perms: Any = workflow.get("permissions")
    assert perms == {"contents": "read"}, (
        f"cosign-verify.yml workflow-level permissions must be exactly "
        f"{{'contents': 'read'}} (least privilege); got {perms!r}"
    )


def test_cosign_verify_no_id_token_write(workflow: dict[str, Any]) -> None:
    """No permissions block (workflow-level or per-job) may grant id-token: write.

    This is the LOAD-BEARING test for Pitfall #1 — PR-triggered workflows must
    not be able to mint OIDC tokens.
    """
    # Check workflow-level permissions
    wf_perms: Any = workflow.get("permissions", {})
    if isinstance(wf_perms, dict):
        assert wf_perms.get("id-token") != "write", (
            "Pitfall #1 violation: workflow-level permissions.id-token must not be 'write' "
            "in a pull_request-triggered workflow"
        )
    # Check per-job permissions
    jobs: dict[str, Any] = workflow.get("jobs", {})
    for job_name, job_def in jobs.items():
        job_perms: Any = job_def.get("permissions", {})
        if isinstance(job_perms, dict):
            assert job_perms.get("id-token") != "write", (
                f"Pitfall #1 violation: job '{job_name}' permissions.id-token must not be "
                "'write' in a pull_request-triggered workflow"
            )


def test_cosign_verify_installs_cosign_at_pinned_sha(workflow: dict[str, Any]) -> None:
    """cosign-installer step must be pinned to the verified SHA (v4.1.2 per RESEARCH)."""
    steps = _get_verify_steps(workflow)
    cosign_step: dict[str, Any] | None = None
    for step in steps:
        if step.get("uses", "").startswith("sigstore/cosign-installer@"):
            cosign_step = step
            break
    assert cosign_step is not None, (
        "cosign-installer step not found in 'verify' job of cosign-verify.yml"
    )
    uses: str = cosign_step.get("uses", "")
    assert uses.endswith(f"@{COSIGN_INSTALLER_SHA}"), (
        f"cosign-installer must be pinned to SHA '{COSIGN_INSTALLER_SHA}' (v4.1.2); got {uses!r}"
    )


def test_cosign_verify_uses_correct_cert_identity_regexp(workflow: dict[str, Any]) -> None:
    """Workflow env.CERT_IDENTITY_REGEXP must match the repo cert chain."""
    env_block: dict[str, Any] = workflow.get("env", {})
    actual_regexp: str = str(env_block.get("CERT_IDENTITY_REGEXP", ""))
    assert actual_regexp == CERT_IDENTITY_REGEXP, (
        f"CERT_IDENTITY_REGEXP mismatch: expected {CERT_IDENTITY_REGEXP!r}, got {actual_regexp!r}"
    )


def test_cosign_verify_uses_correct_oidc_issuer(workflow: dict[str, Any]) -> None:
    """Workflow env.CERT_OIDC_ISSUER must be the GitHub Actions OIDC issuer URL."""
    env_block: dict[str, Any] = workflow.get("env", {})
    actual_issuer: str = str(env_block.get("CERT_OIDC_ISSUER", ""))
    assert actual_issuer == CERT_OIDC_ISSUER, (
        f"CERT_OIDC_ISSUER mismatch: expected {CERT_OIDC_ISSUER!r}, got {actual_issuer!r}"
    )


def test_cosign_verify_attests_both_sbom_formats(workflow: dict[str, Any]) -> None:
    """At least one step must verify --type spdxjson AND one must verify --type cyclonedx."""
    steps = _get_verify_steps(workflow)
    has_spdx = False
    has_cyclonedx = False
    for step in steps:
        run_script: str = step.get("run", "")
        if "--type spdxjson" in run_script:
            has_spdx = True
        if "--type cyclonedx" in run_script:
            has_cyclonedx = True
    assert has_spdx, (
        "SEC-02 defense-in-depth violation: no step in 'verify' job contains "
        "'--type spdxjson' — SPDX SBOM attestation verification is required"
    )
    assert has_cyclonedx, (
        "SEC-02 defense-in-depth violation: no step in 'verify' job contains "
        "'--type cyclonedx' — CycloneDX SBOM attestation verification is required"
    )


def test_cosign_verify_has_bootstrap_graceful_probe(workflow: dict[str, Any]) -> None:
    """A step with id: probe must exist and guard all verify steps (Open Question 3 resolution).

    The probe step must set both exists=true and exists=false outputs.
    All cosign verify / cosign verify-attestation steps must be guarded by
    ``if: steps.probe.outputs.exists == 'true'``.
    """
    steps = _get_verify_steps(workflow)

    # Find the probe step
    probe_step: dict[str, Any] | None = None
    for step in steps:
        if step.get("id") == "probe":
            probe_step = step
            break
    assert probe_step is not None, (
        "Bootstrap-graceful probe step (id: probe) not found in 'verify' job. "
        "Open Question 3 resolution requires a pre-check before cosign verify."
    )

    probe_run: str = probe_step.get("run", "")
    assert "exists=true" in probe_run, (
        "Probe step must set 'exists=true' output when manifest is found"
    )
    assert "exists=false" in probe_run, (
        "Probe step must set 'exists=false' output when manifest is absent (bootstrap case)"
    )

    # Verify all cosign steps are guarded
    for step in steps:
        run_script: str = step.get("run", "")
        if "cosign verify" in run_script or "cosign verify-attestation" in run_script:
            step_if: str = str(step.get("if", ""))
            assert "steps.probe.outputs.exists" in step_if, (
                f"Step '{step.get('name', '(unnamed)')}' runs cosign verify but is not "
                "guarded by steps.probe.outputs.exists — missing bootstrap-graceful guard"
            )


def test_cosign_verify_concurrency_cancel_in_progress(workflow: dict[str, Any]) -> None:
    """Workflow must have concurrency.cancel-in-progress: true (PR push stacking mitigation)."""
    concurrency: Any = workflow.get("concurrency", {})
    assert isinstance(concurrency, dict), (
        f"concurrency block must be a dict; got {type(concurrency).__name__}"
    )
    assert concurrency.get("cancel-in-progress") is True, (
        f"concurrency.cancel-in-progress must be true (matches ci.yml PR pattern); "
        f"got {concurrency.get('cancel-in-progress')!r}"
    )


def test_cosign_verify_runs_on_ubuntu_pinned(workflow: dict[str, Any]) -> None:
    """verify job must run on ubuntu-24.04 (D4 — NOT ubuntu-latest)."""
    verify_job: dict[str, Any] = workflow.get("jobs", {}).get("verify", {})
    runs_on: Any = verify_job.get("runs-on")
    assert runs_on == "ubuntu-24.04", (
        f"D4 violation: verify job must use 'ubuntu-24.04' (pinned); got {runs_on!r}. "
        "Do not use 'ubuntu-latest' — the pinned label ensures reproducible runner versions."
    )

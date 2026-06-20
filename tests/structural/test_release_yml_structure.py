"""Structural tests for .github/workflows/release.yml (Phase 6 / IMAGE-04 / D4 / Pitfall #2).

Asserts: native ARM runner used, no QEMU emulation, push-by-digest enabled,
workflow-level permissions match the keyless-sign contract.
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

RELEASE_YML_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
)

REQUIRED_WORKFLOW_PERMISSIONS: frozenset[str] = frozenset(
    {"contents", "packages", "id-token", "attestations"}
)

NATIVE_RUNNER_LABELS: frozenset[str] = frozenset({"ubuntu-24.04", "ubuntu-24.04-arm"})

# ---------------------------------------------------------------------------
# Module-level fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def release_workflow() -> dict[str, Any]:
    """Load release.yml once and share across all tests in this module."""
    return yaml.safe_load(RELEASE_YML_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalize_on(on_value: dict[str, Any] | list[str] | str) -> dict[str, Any]:
    """Normalise the `on:` field to a uniform dict shape.

    PyYAML (YAML 1.1) may parse `on:` as the boolean ``True``.  After the
    calling test has extracted the value via :func:`_get_on_block` the result
    is already the *value* (not the key), so we only need to handle:

    - ``dict``  — standard ``on: push: …`` YAML map
    - ``list``  — ``on: [push, pull_request]`` shorthand
    - ``str``   — ``on: push`` single-trigger shorthand

    Returns a dict where each trigger name is a key (values may be empty
    dicts when the original representation carried no sub-keys).
    """
    if isinstance(on_value, dict):
        return on_value
    if isinstance(on_value, list):
        return {item: {} for item in on_value}
    if isinstance(on_value, str):
        return {on_value: {}}
    return {}


def _get_on_block(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the `on:` trigger block, handling PyYAML's YAML-1.1 bool coercion.

    PyYAML (YAML 1.1) parses bare ``on:`` as ``True`` (boolean). The key in
    the parsed dict is therefore ``True``, not the string ``"on"``. We iterate
    all keys to find the trigger block without triggering mypy's strict
    key-type checks.
    """
    # Fast path: key stored as string "on"
    if "on" in workflow:
        return _normalize_on(workflow["on"])
    # Slow path: PyYAML coerced `on` → True; scan all keys
    raw: dict[Any, Any] = dict(workflow)
    for key in raw:
        if key is True:
            return _normalize_on(raw[key])
    return {}


def _all_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten all steps from all jobs in the workflow into a single list."""
    steps: list[dict[str, Any]] = []
    jobs: dict[str, Any] = workflow.get("jobs", {})
    for job_def in jobs.values():
        for step in job_def.get("steps", []):
            steps.append(step)
    return steps


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_release_yml_exists() -> None:
    """release.yml must exist at the expected path."""
    assert RELEASE_YML_PATH.is_file(), f"Expected {RELEASE_YML_PATH} to be a file"


def test_release_workflow_triggers_on_tag_push(release_workflow: dict[str, Any]) -> None:
    """release.yml must trigger on push events filtered to v* tags."""
    on_block = _get_on_block(release_workflow)
    assert "push" in on_block, "Expected 'push' trigger in release.yml"
    push_cfg: dict[str, Any] = on_block["push"] or {}
    tags: list[str] = push_cfg.get("tags", [])
    assert any(t.startswith("v") for t in tags), (
        f"Expected push.tags to include a 'v*' pattern; got {tags}"
    )


def test_release_workflow_does_not_trigger_on_pull_request(
    release_workflow: dict[str, Any],
) -> None:
    """release.yml must NOT trigger on pull_request or pull_request_target (Pitfall #1)."""
    on_block = _get_on_block(release_workflow)
    assert "pull_request" not in on_block, (
        "SECURITY VIOLATION: release.yml must not trigger on pull_request — "
        "id-token:write MUST NOT be available to PR-triggered jobs (Pitfall #1)"
    )
    assert "pull_request_target" not in on_block, (
        "SECURITY VIOLATION: release.yml must not trigger on pull_request_target (Pitfall #1)"
    )


def test_release_workflow_declares_required_permissions(release_workflow: dict[str, Any]) -> None:
    """Workflow-level permissions must include contents/packages/id-token/attestations: write."""
    perms: dict[str, Any] = release_workflow.get("permissions", {})
    missing = REQUIRED_WORKFLOW_PERMISSIONS - set(perms.keys())
    assert not missing, (
        f"release.yml workflow-level permissions missing: {missing}. "
        "Plan 06-04 (sign-and-attest) inherits these from the workflow level."
    )
    for perm in REQUIRED_WORKFLOW_PERMISSIONS:
        assert perms[perm] == "write", f"Expected permissions.{perm}: write, got {perms[perm]!r}"


def test_release_workflow_concurrency_cancel_false(release_workflow: dict[str, Any]) -> None:
    """concurrency.cancel-in-progress must be False to prevent half-pushed release (Pitfall #4)."""
    assert release_workflow.get("concurrency", {}).get("cancel-in-progress") is False, (
        "Pitfall #4 violation: release.yml concurrency.cancel-in-progress must be false — "
        "cancelling a release mid-flight can leave orphaned push artefacts."
    )


def test_release_workflow_has_native_arm_runner(release_workflow: dict[str, Any]) -> None:
    """build matrix must include ubuntu-24.04-arm AND ubuntu-24.04 native runners (D4)."""
    matrix_includes: list[dict[str, Any]] = (
        release_workflow.get("jobs", {})
        .get("build", {})
        .get("strategy", {})
        .get("matrix", {})
        .get("include", [])
    )
    runners = {entry.get("runner") for entry in matrix_includes}
    assert "ubuntu-24.04-arm" in runners, (
        "D4 violation: native ARM runner not declared in build matrix. "
        f"Runners found: {runners}. Expected: ubuntu-24.04-arm "
        "(D4 / RESEARCH §ARM Runner Availability)"
    )
    assert "ubuntu-24.04" in runners, (
        "D4 violation: native amd64 runner not declared in build matrix. "
        f"Runners found: {runners}. Expected: ubuntu-24.04"
    )


def test_release_workflow_does_not_use_qemu(release_workflow: dict[str, Any]) -> None:
    """NO step in release.yml may reference docker/setup-qemu-action (Pitfall #2 / D4)."""
    violations: list[str] = []
    for step in _all_steps(release_workflow):
        uses: str = step.get("uses", "")
        if uses.startswith("docker/setup-qemu-action"):
            violations.append(f"step '{step.get('name', uses)}' uses {uses}")
    assert not violations, (
        "Pitfall #2 violation: QEMU detected in release.yml — multi-arch must use native runners "
        f"per D4 (RESEARCH §Common Pitfalls #2). Violations: {violations}"
    )


def test_release_workflow_uses_push_by_digest(release_workflow: dict[str, Any]) -> None:
    """build-push-action step must declare push-by-digest=true for manifest fan-in (Plan 06-04)."""
    found = False
    for step in _all_steps(release_workflow):
        uses: str = step.get("uses", "")
        if "docker/build-push-action" in uses:
            outputs_str: str = str(step.get("with", {}).get("outputs", ""))
            if "push-by-digest=true" in outputs_str:
                found = True
                break
    assert found, (
        "Plan 06-04 cannot assemble multi-arch manifest without push-by-digest=true "
        "(RESEARCH §Multi-arch Build Matrix Pattern). Ensure the docker/build-push-action "
        "step sets `outputs: type=image,push-by-digest=true,...`"
    )


def test_release_workflow_has_oci_license_annotation(release_workflow: dict[str, Any]) -> None:
    """metadata-action step must declare org.opencontainers.image.licenses=Apache-2.0 (IMAGE-05)."""
    found = False
    for step in _all_steps(release_workflow):
        uses: str = step.get("uses", "")
        if "docker/metadata-action" in uses:
            labels_str: str = str(step.get("with", {}).get("labels", ""))
            if "org.opencontainers.image.licenses=Apache-2.0" in labels_str:
                found = True
                break
    assert found, (
        "IMAGE-05 contract violation: docker/metadata-action step must include "
        "'org.opencontainers.image.licenses=Apache-2.0' in its labels input."
    )


def test_release_workflow_build_job_uses_ubuntu_pinned_runner(
    release_workflow: dict[str, Any],
) -> None:
    """Every matrix include entry must use a pinned native runner label (no ubuntu-latest)."""
    matrix_includes: list[dict[str, Any]] = (
        release_workflow.get("jobs", {})
        .get("build", {})
        .get("strategy", {})
        .get("matrix", {})
        .get("include", [])
    )
    for entry in matrix_includes:
        runner: str = entry.get("runner", "")
        assert runner in NATIVE_RUNNER_LABELS, (
            f"Matrix entry runner '{runner}' is not in the approved set "
            f"{NATIVE_RUNNER_LABELS}. Use ubuntu-24.04 or ubuntu-24.04-arm (D4). "
            "Avoid ubuntu-latest — it is a mutable alias."
        )

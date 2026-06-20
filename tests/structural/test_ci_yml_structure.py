"""Structural tests asserting `.github/workflows/ci.yml` matches CONTEXT D9: 7-job parallel fan-out.
Pitfall #1: no `pull_request`-triggered job requests `id-token: write`.
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

CI_YML_PATH = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"

JOB_NAMES_REQUIRED: frozenset[str] = frozenset(
    {
        "lint-typecheck",
        "unit-coverage",
        "integration",
        "trivy-image",
        "trivy-dockerfile",
        "pip-audit",
        "acceptance",
    }
)

# ---------------------------------------------------------------------------
# Module-level fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ci_workflow() -> dict[str, Any]:
    """Load ci.yml once and share across all tests in this module."""
    return yaml.safe_load(CI_YML_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ci_yml_exists() -> None:
    """ci.yml must exist at the expected path."""
    assert CI_YML_PATH.is_file(), f"Expected {CI_YML_PATH} to be a file"


def test_ci_workflow_has_seven_required_jobs(ci_workflow: dict[str, Any]) -> None:
    """ci.yml must declare all 7 D9 parallel fan-out jobs (CONTEXT D9 / CI-01)."""
    jobs: dict[str, Any] = ci_workflow.get("jobs", {})
    missing = JOB_NAMES_REQUIRED - set(jobs.keys())
    assert not missing, f"Missing jobs: {missing}"


def test_ci_workflow_declares_minimal_permissions(ci_workflow: dict[str, Any]) -> None:
    """Workflow-level permissions must be exactly `contents: read` (least-privilege)."""
    assert ci_workflow.get("permissions") == {"contents": "read"}, (
        f"Expected permissions: {{contents: read}}, got: {ci_workflow.get('permissions')}"
    )


def test_ci_workflow_has_concurrency_block(ci_workflow: dict[str, Any]) -> None:
    """ci.yml must declare a concurrency block with cancel-in-progress: true (T-06-04)."""
    assert "concurrency" in ci_workflow, "Expected 'concurrency' block in ci.yml"
    assert ci_workflow["concurrency"].get("cancel-in-progress") is True, (
        "Expected concurrency.cancel-in-progress: true"
    )


def test_no_job_requests_id_token(ci_workflow: dict[str, Any]) -> None:
    """No PR-triggered job may request id-token: write (Pitfall #1 / T-06-V4-OIDC)."""
    jobs: dict[str, Any] = ci_workflow.get("jobs", {})
    for job_name, job_def in jobs.items():
        id_token_val = (job_def.get("permissions") or {}).get("id-token")
        assert id_token_val is None, (
            f"Pitfall #1 VIOLATION: job '{job_name}' requests id-token in a"
            " pull_request-triggered workflow — see RESEARCH §Common Pitfalls"
        )


def _get_on_block(ci_workflow: dict[str, Any]) -> Any:
    """Return the `on:` trigger block, handling PyYAML's YAML-1.1 boolean coercion.

    PyYAML (YAML 1.1) parses bare `on:` as `True` (boolean). The key in the
    parsed dict is therefore `True`, not the string `"on"`. We iterate all keys
    to find the trigger block without triggering mypy's strict key-type checks.
    """
    # Fast path: key is stored as string "on"
    if "on" in ci_workflow:
        return ci_workflow["on"]
    # Slow path: PyYAML coerced `on` → True (YAML 1.1 bool); scan all keys
    raw: dict[Any, Any] = dict(ci_workflow)
    for key in raw:
        if key is True:
            return raw[key]
    return {}


def test_ci_workflow_triggers_on_pull_request(ci_workflow: dict[str, Any]) -> None:
    """ci.yml must trigger on pull_request events."""
    on_block = _get_on_block(ci_workflow)
    # YAML `on:` can parse as True (boolean) in some loaders; handle both dict and list shapes.
    if isinstance(on_block, (dict, list)):
        assert "pull_request" in on_block, "Expected 'pull_request' trigger in ci.yml"
    else:
        pytest.fail(f"Unexpected 'on:' block shape: {type(on_block)}")


def test_ci_workflow_does_not_use_pull_request_target(ci_workflow: dict[str, Any]) -> None:
    """ci.yml must NOT use pull_request_target trigger (security antipattern / T-06-V4-PT)."""
    on_block = _get_on_block(ci_workflow)
    if isinstance(on_block, (dict, list)):
        assert "pull_request_target" not in on_block, (
            "SECURITY VIOLATION: pull_request_target trigger detected in ci.yml"
            " — see RESEARCH §Known Threat Patterns"
        )

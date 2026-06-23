"""Structural tests for the sign-and-attest job in .github/workflows/release.yml.

Phase 6 / SEC-01 / SEC-02 / SEC-03 / CI-03. Asserts: cosign keyless (registry-side bundle in 2.x),
both SBOM formats attested, SLSA provenance via attest-build-provenance@v4 (RESEARCH C1).
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

# SHAs from 06-RESEARCH.md "Action Digest Resolution" (verified via gh api 2026-06-20)
COSIGN_INSTALLER_SHA = "6f9f17788090df1f26f669e9d70d6ae9567deba6"  # v4.1.2
SBOM_ACTION_SHA = "e22c389904149dbc22b58101806040fa8d37a610"  # v0.24.0
# v4.1.0 — RESEARCH C1 correction: NOT @v1
ATTEST_BUILD_PROVENANCE_SHA = "a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32"

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


def _get_sign_attest_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of steps in the sign-and-attest job."""
    job: dict[str, Any] = workflow.get("jobs", {}).get("sign-and-attest", {})
    return list(job.get("steps", []))


def _step_has_uses(steps: list[dict[str, Any]], action_prefix: str) -> dict[str, Any] | None:
    """Return the first step whose ``uses`` starts with ``action_prefix``, or None."""
    for step in steps:
        uses: str = step.get("uses", "")
        if uses.startswith(action_prefix):
            return step
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sign_attest_job_exists(release_workflow: dict[str, Any]) -> None:
    """sign-and-attest job must exist in release.yml jobs."""
    assert "sign-and-attest" in release_workflow.get("jobs", {}), (
        "sign-and-attest job not found in release.yml — Plan 06-04 failed to append the job"
    )


def test_sign_attest_job_needs_build(release_workflow: dict[str, Any]) -> None:
    """sign-and-attest must declare needs: [build] to fan-in after the build matrix."""
    needs_value = release_workflow["jobs"]["sign-and-attest"].get("needs")
    # YAML may parse single-value list as either a list or a bare string
    if isinstance(needs_value, list):
        assert "build" in needs_value, (
            f"sign-and-attest.needs must include 'build'; got {needs_value}"
        )
    else:
        assert needs_value == "build", (
            f"sign-and-attest.needs must be 'build' or ['build']; got {needs_value!r}"
        )


def test_sign_attest_declares_id_token_write(release_workflow: dict[str, Any]) -> None:
    """sign-and-attest must declare id-token: write — enables OIDC token for Fulcio cert."""
    perms: dict[str, Any] = release_workflow["jobs"]["sign-and-attest"].get("permissions", {})
    assert perms.get("id-token") == "write", (
        f"SEC-01 enabling condition: sign-and-attest must have permissions.id-token: write; "
        f"got {perms.get('id-token')!r}"
    )


def test_sign_attest_declares_attestations_write(release_workflow: dict[str, Any]) -> None:
    """sign-and-attest must declare attestations: write — required for SLSA provenance (SEC-03)."""
    perms: dict[str, Any] = release_workflow["jobs"]["sign-and-attest"].get("permissions", {})
    assert perms.get("attestations") == "write", (
        f"SEC-03 enabling condition: sign-and-attest must have permissions.attestations: write; "
        f"got {perms.get('attestations')!r}"
    )


def test_sign_attest_installs_cosign_at_pinned_sha(release_workflow: dict[str, Any]) -> None:
    """cosign-installer step must be pinned to the verified SHA (v4.1.2 per RESEARCH)."""
    steps = _get_sign_attest_steps(release_workflow)
    step = _step_has_uses(steps, "sigstore/cosign-installer@")
    assert step is not None, "cosign-installer step not found in sign-and-attest job"
    uses: str = step.get("uses", "")
    assert uses.endswith(f"@{COSIGN_INSTALLER_SHA}"), (
        f"cosign-installer must be pinned to SHA {COSIGN_INSTALLER_SHA}; got {uses!r}"
    )


def test_sign_attest_installs_cosign_v_2_6_3(release_workflow: dict[str, Any]) -> None:
    """cosign-installer must pin cosign-release to v2.6.3 — Dockerfile Phase 4 D8 carry-forward."""
    steps = _get_sign_attest_steps(release_workflow)
    step = _step_has_uses(steps, "sigstore/cosign-installer@")
    assert step is not None, "cosign-installer step not found in sign-and-attest job"
    cosign_release: str = step.get("with", {}).get("cosign-release", "")
    assert cosign_release == "v2.6.3", (
        f"cosign-installer must pin cosign-release to 'v2.6.3' (Phase 4 D8); got {cosign_release!r}"
    )


def test_sign_attest_has_cosign_sign_step(release_workflow: dict[str, Any]) -> None:
    """A cosign sign step against the image manifest must exist (SEC-01).

    Cosign 2.x stores signature + cert + Rekor inclusion proof as OCI artifacts
    alongside the image in the registry; no local `--bundle` file is required.
    The v1.x `--bundle` flag was removed from `cosign sign` in 2.x.
    Consumers fetch the registry-side bundle for offline verify via
    ``cosign download signature ${IMAGE_REF} > cosign.bundle``.
    """
    steps = _get_sign_attest_steps(release_workflow)
    found = False
    for step in steps:
        run_script: str = step.get("run", "")
        if "cosign sign" in run_script and "--yes" in run_script:
            found = True
            # Guard against re-introducing the v1.x --bundle flag (regression check).
            assert "--bundle" not in run_script, (
                "cosign 2.x: `cosign sign` does NOT accept `--bundle` (removed). "
                "Use registry-side artifacts; see SEC-01 step comment."
            )
            break
    assert found, (
        "SEC-01 violation: no `cosign sign --yes <image>` step found in sign-and-attest job. "
        "Cosign 2.x keyless image signing requires this exact invocation shape."
    )


def test_sign_attest_generates_spdx_sbom(release_workflow: dict[str, Any]) -> None:
    """anchore/sbom-action step with format: spdx-json must exist (SEC-02 / D8)."""
    steps = _get_sign_attest_steps(release_workflow)
    found = False
    for step in steps:
        uses: str = step.get("uses", "")
        if uses.startswith(f"anchore/sbom-action@{SBOM_ACTION_SHA}"):
            fmt: str = step.get("with", {}).get("format", "")
            if fmt == "spdx-json":
                found = True
                break
    assert found, (
        f"SEC-02 violation: no anchore/sbom-action@{SBOM_ACTION_SHA} step with "
        "format: spdx-json found in sign-and-attest job"
    )


def test_sign_attest_generates_cyclonedx_sbom(release_workflow: dict[str, Any]) -> None:
    """anchore/sbom-action step with format: cyclonedx-json must exist (SEC-02 / D8)."""
    steps = _get_sign_attest_steps(release_workflow)
    found = False
    for step in steps:
        uses: str = step.get("uses", "")
        if uses.startswith(f"anchore/sbom-action@{SBOM_ACTION_SHA}"):
            fmt: str = step.get("with", {}).get("format", "")
            if fmt == "cyclonedx-json":
                found = True
                break
    assert found, (
        f"SEC-02 violation: no anchore/sbom-action@{SBOM_ACTION_SHA} step with "
        "format: cyclonedx-json found in sign-and-attest job"
    )


def test_sign_attest_attests_spdx_via_cosign(release_workflow: dict[str, Any]) -> None:
    """A cosign attest step with --type spdxjson must exist (CONTEXT D8 contract)."""
    steps = _get_sign_attest_steps(release_workflow)
    found = False
    for step in steps:
        run_script: str = step.get("run", "")
        if "cosign attest" in run_script and "--type spdxjson" in run_script:
            found = True
            break
    assert found, (
        "D8 violation: no 'cosign attest --type spdxjson' step found in sign-and-attest job. "
        "D8 contract: SBOM must be attested (not just signed) — attestation is the signed delivery."
    )


def test_sign_attest_attests_cyclonedx_via_cosign(release_workflow: dict[str, Any]) -> None:
    """A cosign attest step with --type cyclonedx must exist (CONTEXT D8 contract)."""
    steps = _get_sign_attest_steps(release_workflow)
    found = False
    for step in steps:
        run_script: str = step.get("run", "")
        if "cosign attest" in run_script and "--type cyclonedx" in run_script:
            found = True
            break
    assert found, (
        "D8 violation: no 'cosign attest --type cyclonedx' step found in sign-and-attest job. "
        "D8 contract: CycloneDX SBOM must be attested via cosign attest."
    )


def test_sign_attest_uses_attest_build_provenance_v4(release_workflow: dict[str, Any]) -> None:
    """attest-build-provenance step must be pinned to v4.1.0 SHA — RESEARCH C1 (NOT @v1)."""
    steps = _get_sign_attest_steps(release_workflow)
    step = _step_has_uses(steps, "actions/attest-build-provenance@")
    assert step is not None, (
        "actions/attest-build-provenance step not found in sign-and-attest job (SEC-03)"
    )
    uses: str = step.get("uses", "")
    assert uses.endswith(f"@{ATTEST_BUILD_PROVENANCE_SHA}"), (
        f"RESEARCH C1 violation: attest-build-provenance must be pinned to v4.1.0 SHA "
        f"'{ATTEST_BUILD_PROVENANCE_SHA}' (NOT @v1). Got: {uses!r}"
    )


def test_sign_attest_manifest_assembly_has_three_tags(release_workflow: dict[str, Any]) -> None:
    """imagetools create step must apply three tags: vX.Y.Z, :MAJOR (rolling), :latest (MIG-01)."""
    steps = _get_sign_attest_steps(release_workflow)
    imagetools_step: dict[str, Any] | None = None
    for step in steps:
        run_script: str = step.get("run", "")
        if "docker buildx imagetools create" in run_script:
            imagetools_step = step
            break
    assert imagetools_step is not None, (
        "MIG-01 violation: no 'docker buildx imagetools create' step found in sign-and-attest job"
    )
    run_script = imagetools_step.get("run", "")
    assert '--tag "${IMAGE}:${VERSION}"' in run_script, (
        f'MIG-01 violation: imagetools create step must include --tag "${{IMAGE}}:${{VERSION}}"; '
        f"run script:\n{run_script}"
    )
    assert '--tag "${IMAGE}:${MAJOR}"' in run_script, (
        f'MIG-01 violation: imagetools create step must include --tag "${{IMAGE}}:${{MAJOR}}" '
        f"(rolling-major tag per MIG-01); run script:\n{run_script}"
    )
    assert '--tag "${IMAGE}:latest"' in run_script, (
        f'MIG-01 violation: imagetools create step must include --tag "${{IMAGE}}:latest"; '
        f"run script:\n{run_script}"
    )


def test_sign_attest_has_qemu_smoke_check(release_workflow: dict[str, Any]) -> None:
    """Smoke-test step must detect unknown platforms while ignoring attestation-manifests.

    Pitfall #2 guard: a real (non-attestation) manifest entry with
    platform=unknown/unknown is the QEMU-broken arm64 telltale. SLSA attestation
    manifests legitimately carry platform=unknown/unknown plus annotation
    ``vnd.docker.reference.type=attestation-manifest`` and must NOT trigger the
    guard. The check uses ``jq`` on ``--raw`` JSON output to distinguish.
    """
    steps = _get_sign_attest_steps(release_workflow)
    smoke_step: dict[str, Any] | None = None
    for step in steps:
        run_script: str = step.get("run", "")
        if "attestation-manifest" in run_script and "imagetools inspect" in run_script:
            smoke_step = step
            break
    assert smoke_step is not None, (
        "Pitfall #2 guard missing: no step in sign-and-attest filters out "
        "'attestation-manifest' before checking for unknown platforms — this is "
        "required so SLSA attestation manifests don't false-trip the QEMU broken-arm64 guard."
    )
    run_script = smoke_step.get("run", "")
    assert "linux/amd64" in run_script, (
        f"Smoke-test step must assert 'linux/amd64' present in manifest inspect output; "
        f"run script:\n{run_script}"
    )
    assert "linux/arm64" in run_script, (
        f"Smoke-test step must assert 'linux/arm64' present in manifest inspect output; "
        f"run script:\n{run_script}"
    )
    assert "unknown" in run_script, (
        f"Smoke-test step must still check for unknown platforms (the QEMU bug); "
        f"run script:\n{run_script}"
    )

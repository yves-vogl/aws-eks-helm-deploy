"""Integration smoke test: helm version check against a kind cluster.

Phase 1 smoke — proves kind+helm wiring is operational.
Real helm-on-cluster deploys land in Phase 3 (CHART-01).

This test:
  - Requires the ``kind_cluster`` session fixture (which skips if kind/helm
    is absent from the host PATH).
  - Calls ``helm version --short`` and asserts the binary reports a v4.x line
    (matches Dockerfile HELM_VERSION=4.2.2 pin per issue #70 migration).
  - Does NOT exercise helm against the cluster API at Phase 1 level; that
    requires a kubeconfig update and lands in the Phase 3 UpgradeAction tests.
"""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.integration
def test_helm_version_in_cluster(kind_cluster: str) -> None:
    """Verify helm binary is accessible and reports v4.x while the kind cluster exists.

    Phase 1 smoke — proves kind+helm wiring is operational.
    Real helm-on-cluster deploys land in Phase 3 (CHART-01).

    The pipe migrated to helm v4 in issue #70 (ADR-0010) ahead of the Helm v3 EOL
    on 2026-11-11. This assertion guards against an accidental runtime downgrade
    of the kind-test job — the Dockerfile HELM_VERSION pin and the
    azure/setup-helm pin in ci.yml MUST move together.

    Args:
        kind_cluster: The name of the running kind cluster (provided by the
            session-scoped fixture in conftest.py).
    """
    result = subprocess.run(
        ["helm", "version", "--short"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"helm version --short failed:\n{result.stderr}"
    assert "v4." in result.stdout, f"Expected 'v4.' in helm version output, got: {result.stdout!r}"

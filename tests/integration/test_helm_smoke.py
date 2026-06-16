"""Integration smoke test: helm version check against a kind cluster.

Phase 1 smoke — proves kind+helm wiring is operational.
Real helm-on-cluster deploys land in Phase 3 (CHART-01).

This test:
  - Requires the ``kind_cluster`` session fixture (which skips if kind/helm
    is absent from the host PATH).
  - Calls ``helm version --short`` and asserts the binary reports a v3.x line.
  - Does NOT exercise helm against the cluster API at Phase 1 level; that
    requires a kubeconfig update and lands in the Phase 3 UpgradeAction tests.
"""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.integration
def test_helm_version_in_cluster(kind_cluster: str) -> None:
    """Verify helm binary is accessible and reports v3.x while the kind cluster exists.

    Phase 1 smoke — proves kind+helm wiring is operational.
    Real helm-on-cluster deploys land in Phase 3 (CHART-01).

    Args:
        kind_cluster: The name of the running kind cluster (provided by the
            session-scoped fixture in conftest.py).
    """
    result = subprocess.run(
        ["helm", "version", "--short"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"helm version --short failed:\n{result.stderr}"
    assert "v3." in result.stdout, f"Expected 'v3.' in helm version output, got: {result.stdout!r}"

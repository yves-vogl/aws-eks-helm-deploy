"""Session-scoped kind cluster fixture for the integration test tier.

The ``kind_cluster`` fixture:
  - Skips the entire integration test session if ``kind`` or ``helm`` is not
    on the host PATH (graceful no-op for developer machines without kind).
  - Creates a kind cluster named ``test-pipe-integration`` before the session.
  - Yields the cluster name string to each test that requests the fixture.
  - Tears the cluster down unconditionally on session exit (``check=False``
    on the delete side handles the "cluster was never fully created" case).

Phase 1 smoke only — real helm-on-cluster deploys land in Phase 3 (CHART-01).
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator

import pytest

_CLUSTER_NAME = "test-pipe-integration"


@pytest.fixture(scope="session")
def kind_cluster() -> Iterator[str]:
    """Create and tear down a kind cluster for the integration session.

    Skips if ``kind`` or ``helm`` is not installed on the host.
    """
    if shutil.which("kind") is None:
        pytest.skip("kind not installed — integration tier skipped (install via brew install kind)")

    if shutil.which("helm") is None:
        pytest.skip("helm not installed — integration tier skipped (install via brew install helm)")

    try:
        subprocess.run(
            ["kind", "create", "cluster", "--name", _CLUSTER_NAME],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"kind cluster creation failed: {exc.stderr}")

    try:
        yield _CLUSTER_NAME
    finally:
        subprocess.run(
            ["kind", "delete", "cluster", "--name", _CLUSTER_NAME],
            check=False,
            capture_output=True,
        )

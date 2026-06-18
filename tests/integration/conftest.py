"""Session-scoped kind cluster fixtures for the integration test tier.

The ``kind_cluster`` fixture (Phase 1):
  - Skips the entire integration test session if ``kind`` or ``helm`` is not
    on the host PATH (graceful no-op for developer machines without kind).
  - Creates a kind cluster named ``test-pipe-integration`` before the session.
  - Yields the cluster name string to each test that requests the fixture.
  - Tears the cluster down unconditionally on session exit (``check=False``
    on the delete side handles the "cluster was never fully created" case).

The ``kind_kubeconfig`` fixture (Plan 03-05):
  - Depends on ``kind_cluster`` — runs ``kind get kubeconfig --name <name>``
    and writes the output to a tempfile with ``chmod 0600``.
  - Yields a ``pathlib.Path`` to the tempfile kubeconfig.
  - Cleans up on session exit via ``path.unlink()``.
  - Skips cleanly if ``kind get kubeconfig`` fails.
  - Used by ``tests/integration/test_upgrade_action.py`` via the
    ``UpgradeAction(settings, kubeconfig_override=kind_kubeconfig)`` scaffold.
    Kind's kube-apiserver does NOT accept EKS bearer tokens; the override
    bypasses EKS token generation entirely (RESEARCH Section C + CONTEXT D10).
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import subprocess
import tempfile
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
            timeout=180,
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
            timeout=60,
        )


@pytest.fixture(scope="session")
def kind_kubeconfig(kind_cluster: str) -> Iterator[pathlib.Path]:
    """Extract kind's admin kubeconfig to a secure tempfile and yield its path.

    Runs ``kind get kubeconfig --name <cluster>`` and writes the resulting YAML
    to a tempfile with ``chmod 0600``. The tempfile is deleted on session exit.

    Kind's kube-apiserver does NOT accept EKS bearer tokens or moto-presigned
    URLs. This fixture provides the kind-native admin kubeconfig so that
    ``UpgradeAction(settings, kubeconfig_override=<path>)`` can bypass the
    EKS token and ``write_kubeconfig`` steps entirely (CONTEXT D10 + RESEARCH
    Section C definitive finding).

    Skips cleanly if ``kind get kubeconfig`` fails — mirrors the ``kind_cluster``
    fixture's skip-on-failure contract so the session exits 0 without kind.

    Args:
        kind_cluster: The name of the running kind cluster (session fixture).

    Yields:
        pathlib.Path to a ``chmod 0600`` tempfile containing the kubeconfig YAML.
    """
    try:
        result = subprocess.run(
            ["kind", "get", "kubeconfig", "--name", kind_cluster],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"kind get kubeconfig failed: {exc.stderr}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        prefix="kind-kubeconfig-",
    ) as tmp:
        path = pathlib.Path(tmp.name)
    os.chmod(path, 0o600)
    path.write_text(result.stdout)
    try:
        yield path
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()

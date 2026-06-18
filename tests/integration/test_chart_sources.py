"""Integration tests for ChartSource implementations (Phase 4).

Plan 04-06 ships the RepoChart test. Plan 04-07 EXTENDS this file with OciChart
tests (against a local ``registry:2`` container fixture).

Test isolation:
    The ``local_helm_repo`` fixture spins up a ``python -m http.server`` process
    serving a local helm repo built from the Phase 3 minimal chart fixture at
    ``tests/fixtures/charts/minimal/``. No Docker or kind required for these tests
    — only the ``helm`` binary must be on PATH.

    The ``oci_registry`` fixture spins up a Docker ``registry:2`` container on
    localhost:5555. Requires Docker on PATH.

Skip conditions:
    - ``helm`` binary not on PATH → session-level skips.
    - ``docker`` binary not on PATH or registry:2 not ready → session-level skips.
    - Server startup within 15 s → test skipped with ``pytest.skip``.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from aws_eks_helm_deploy.chart.oci import OciChart
from aws_eks_helm_deploy.chart.repo import RepoChart

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_REPO_PORT = 17855


@pytest.fixture(scope="session")
def local_helm_repo(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Build a minimal in-process Helm repo on disk and serve it via python -m http.server.

    Steps:
      1. ``helm package tests/fixtures/charts/minimal -d <repo_dir>``
      2. ``helm repo index <repo_dir>``
      3. ``python -m http.server <port> --bind 127.0.0.1`` from <repo_dir>
      4. Wait up to 15 s for the server to accept connections.

    Yields:
        The repo URL ``http://127.0.0.1:<port>``.

    Skips cleanly if ``helm`` binary is unavailable or the server does not start.
    """
    if shutil.which("helm") is None:
        pytest.skip("helm binary not installed; integration tier requires it")

    # Use the Phase 3 minimal chart fixture (Chart.yaml + templates/configmap.yaml)
    fixtures_root = Path(__file__).parent.parent / "fixtures" / "charts" / "minimal"
    if not fixtures_root.is_dir():
        pytest.skip(f"fixtures/charts/minimal not found at {fixtures_root}")

    repo_dir = tmp_path_factory.mktemp("helm-repo")

    # Package the chart
    try:
        subprocess.run(
            ["helm", "package", str(fixtures_root), "-d", str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"helm package failed: {exc.stderr}")

    # Build the index
    try:
        subprocess.run(
            ["helm", "repo", "index", str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"helm repo index failed: {exc.stderr}")

    # Serve via python -m http.server on a fixed port
    proc = subprocess.Popen(
        ["python", "-m", "http.server", str(_REPO_PORT), "--bind", "127.0.0.1"],
        cwd=repo_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for the server to accept connections (poll /index.yaml)
        ready = False
        for _ in range(30):
            check = subprocess.run(
                ["curl", "-sf", f"http://127.0.0.1:{_REPO_PORT}/index.yaml"],
                capture_output=True,
                timeout=2,
            )
            if check.returncode == 0:
                ready = True
                break
            time.sleep(0.5)

        if not ready:
            pytest.skip("local helm-repo server did not start within 15 s")

        yield f"http://127.0.0.1:{_REPO_PORT}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


_OCI_REGISTRY_PORT = 5555


@pytest.fixture(scope="session")
def oci_registry() -> Iterator[str]:
    """Spawn a local docker registry:2 on 127.0.0.1:5555 for OCI chart tests.

    Skips cleanly when docker is unavailable or registry:2 cannot start within 15 s.
    Yields the registry host string ``"127.0.0.1:5555"``.
    """
    if shutil.which("docker") is None:
        pytest.skip("docker not installed; OCI integration tier requires it")

    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-p",
                f"{_OCI_REGISTRY_PORT}:5000",
                "registry:2",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"docker run registry:2 failed: {exc.stderr}")

    container_id = result.stdout.strip()
    try:
        for _ in range(30):
            r = subprocess.run(
                ["curl", "-sf", f"http://127.0.0.1:{_OCI_REGISTRY_PORT}/v2/"],
                capture_output=True,
                timeout=2,
            )
            if r.returncode == 0:
                break
            time.sleep(0.5)
        else:
            pytest.skip("registry:2 did not become ready within 15 s")

        yield f"127.0.0.1:{_OCI_REGISTRY_PORT}"
    finally:
        subprocess.run(
            ["docker", "stop", container_id],
            check=False,
            capture_output=True,
            timeout=15,
        )


@pytest.mark.integration
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_repo_chart_resolves_real_chart_via_local_http_repo(local_helm_repo: str) -> None:
    """RepoChart resolves the minimal chart from a local helm HTTP repo.

    Asserts:
        - resolved.name matches the chart's Chart.yaml name field ("minimal")
        - resolved.version matches the chart's Chart.yaml version field ("0.1.0")
        - resolved.source_path is a directory containing Chart.yaml (inside the context)
        - After the with block, the tempdir is cleaned up (source_path no longer exists)
    """
    chart_source = RepoChart(
        name="local",
        chart="minimal",
        repo_url=local_helm_repo,
        version="0.1.0",
    )
    with chart_source.resolve() as resolved:
        assert resolved.name == "minimal"
        assert resolved.version == "0.1.0"
        assert resolved.source_path.is_dir()
        assert (resolved.source_path / "Chart.yaml").exists()

    # After context exit, the tempdir is cleaned up
    assert not resolved.source_path.exists()


# ---------------------------------------------------------------------------
# OciChart integration tests (Plan 04-07)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_oci_chart_pulls_from_local_registry_2(oci_registry: str) -> None:
    """OciChart pulls the minimal chart from a local registry:2.

    Asserts:
        - resolved.name == "minimal"
        - resolved.version == "0.1.0"
        - resolved.source_path is a directory
        - After the with block, the tempdir is cleaned up
    """
    if shutil.which("helm") is None:
        pytest.skip("helm binary not installed")

    fixtures_root = Path(__file__).parent.parent / "fixtures" / "charts" / "minimal"
    if not fixtures_root.is_dir():
        pytest.skip(f"fixtures/charts/minimal not found at {fixtures_root}")

    # Package the chart into /tmp/
    try:
        subprocess.run(
            ["helm", "package", str(fixtures_root), "-d", "/tmp/"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"helm package failed: {exc.stderr}")

    # Push to the local registry:2
    try:
        subprocess.run(
            [
                "helm",
                "push",
                "/tmp/minimal-0.1.0.tgz",
                f"oci://{oci_registry}/charts",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"helm push failed: {exc.stderr}")

    chart_source = OciChart(
        reference=f"{oci_registry}/charts/minimal",
        version="0.1.0",
    )
    with chart_source.resolve() as resolved:
        assert resolved.name == "minimal"
        assert resolved.version == "0.1.0"
        assert resolved.source_path.is_dir()
        assert (resolved.source_path / "Chart.yaml").exists()

    assert not resolved.source_path.exists()


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("cosign") is None, reason="cosign not installed")
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_oci_chart_verify_against_signed_test_chart(oci_registry: str) -> None:
    """OciChart with verify=True verifies a Cosign-signed chart from a local registry.

    Gated: requires the ``cosign`` binary AND an OIDC token for keyless signing.
    Local dev typically can't run this without manual setup; CI environments with
    OIDC tokens (e.g. GitHub Actions) can automate it.

    Deviation 1 (Plan 04-07): this test ships as a SKIPPED PLACEHOLDER. The
    cosign verify code path is fully covered by unit tests via subprocess mocking.
    Phase 6 / v2.1 will fill in the signing-at-fixture-time logic using the same
    OIDC token pattern established for SEC-01 (image signing).
    """
    pytest.skip("Cosign-signed chart fixture requires OIDC token; Phase 6 / v2.1 will automate")

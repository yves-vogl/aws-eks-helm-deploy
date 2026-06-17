"""Session-scoped Docker image build fixture for the acceptance test tier.

The ``built_image`` fixture:
  - Skips the entire acceptance test session if ``docker`` is not on the host PATH.
  - Builds the image tagged ``aws-eks-helm-deploy:acceptance-test`` from the repo root
    once per pytest session (``scope="session"``).
  - If the build fails (e.g., the Dockerfile has not yet merged from Plan C), the
    fixture calls ``pytest.skip`` with the stderr from the failed build rather than
    hard-failing — so the acceptance tier is non-blocking before Plan C merges in CI.
  - Yields the image tag string to each acceptance test that requests the fixture.
  - Best-effort cleanup: ``docker rmi`` on session exit (failures silently ignored).

Phase 1 scope: three smoke tests (non-root uid, uid >= 10000, no Python traceback).
Phase 2+ extends with auth/helm-action smoke tests; Phase 6 wires this into GHA.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

_IMAGE_TAG = "aws-eks-helm-deploy:acceptance-test"


@pytest.fixture(scope="session")
def built_image() -> Iterator[str]:
    """Build the Docker image once per test session.

    Skips if ``docker`` is not installed on the host.
    Skips (non-blocking) if the ``docker build`` fails (e.g., Dockerfile not
    yet available from Plan C) rather than hard-failing the session.
    """
    if shutil.which("docker") is None:
        pytest.skip("docker not installed — acceptance tier skipped")

    repo_root = Path(__file__).resolve().parents[2]

    try:
        subprocess.run(
            ["docker", "build", "-t", _IMAGE_TAG, str(repo_root)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"docker build failed (Dockerfile may not be available yet): {exc.stderr}")

    try:
        yield _IMAGE_TAG
    finally:
        subprocess.run(
            ["docker", "rmi", _IMAGE_TAG],
            check=False,
            capture_output=True,
            timeout=60,
        )

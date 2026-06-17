"""Session-scoped Docker image build fixture for the acceptance test tier.

The ``built_image`` fixture:
  - Skips the entire acceptance test session if ``docker`` is not on the host PATH.
  - Checks whether the Docker daemon is reachable; if not, skips (daemon not running).
  - Builds the image tagged ``aws-eks-helm-deploy:acceptance-test`` from the repo root
    once per pytest session (``scope="session"``).
  - If ``docker`` IS available and the build FAILS, the fixture calls ``pytest.fail``
    so CI surfaces the regression rather than masking it with a silent skip.  This
    prevents the sec-08 class of bug (broken Dockerfile silently bypassed by skip).
  - Yields the image tag string to each acceptance test that requests the fixture.
  - Best-effort cleanup: ``docker rmi`` on session exit (failures silently ignored).

Phase 1 scope: four smoke tests (non-root uid, uid >= 10000, no Python traceback,
curl purged, git purged).
Phase 2+ extends with auth/helm-action smoke tests; Phase 6 wires this into GHA.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

_IMAGE_TAG = "aws-eks-helm-deploy:acceptance-test"


def _docker_daemon_available() -> bool:
    """Return True if the Docker daemon is reachable."""
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        timeout=10,
    )
    return result.returncode == 0


@pytest.fixture(scope="session")
def built_image() -> Iterator[str]:
    """Build the Docker image once per test session.

    Skips if ``docker`` is not installed on the host or the daemon is not running.
    Hard-fails (``pytest.fail``) if ``docker`` IS available but ``docker build``
    fails — a build failure with a live daemon is a real regression, not an
    infrastructure gap, and must not be silently swallowed.
    """
    if shutil.which("docker") is None:
        pytest.skip("docker not installed — acceptance tier skipped")

    if not _docker_daemon_available():
        pytest.skip("docker daemon not reachable — acceptance tier skipped")

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
        pytest.fail(f"docker build failed — Dockerfile is broken (fix before merge):\n{exc.stderr}")

    try:
        yield _IMAGE_TAG
    finally:
        subprocess.run(
            ["docker", "rmi", _IMAGE_TAG],
            check=False,
            capture_output=True,
            timeout=60,
        )

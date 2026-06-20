"""Acceptance test: the built runtime image bundles cosign 2.6.3 in /usr/local/bin/.

Requirements traceability:
    CHART-04 (Phase 4): cosign must be present in the runtime image to support
    ``CHART_VERIFY=true`` inside the container.

Skip condition:
    - ``docker`` binary not on PATH or Docker daemon not reachable → acceptance tier
      is skipped via the ``built_image`` fixture in ``tests/acceptance/conftest.py``.

Coverage tier:
    This test proves the supply-chain claim at the IMAGE tier. The cosign verify code
    path is covered at the unit tier by ``tests/unit/test_chart_oci.py``.
"""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.acceptance
def test_cosign_binary_in_path(built_image: str) -> None:
    """cosign is reachable as a binary inside the runtime image at /usr/local/bin/cosign.

    Asserts:
        - ``which cosign`` exits 0 and returns ``/usr/local/bin/cosign``
        - ``cosign version`` exits 0 and prints ``GitVersion`` (cosign 2.x version output)
    """
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "/bin/sh",
            built_image,
            "-c",
            "which cosign && cosign version",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"cosign not reachable in image '{built_image}':\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "/usr/local/bin/cosign" in result.stdout, (
        f"Expected '/usr/local/bin/cosign' in stdout, got: {result.stdout}"
    )
    assert "GitVersion" in result.stdout, (
        f"Expected 'GitVersion' in cosign version output, got: {result.stdout}"
    )

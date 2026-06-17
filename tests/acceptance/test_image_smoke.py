"""Acceptance smoke tests for the aws-eks-helm-deploy Docker image.

All tests are marked ``@pytest.mark.acceptance`` and require the ``built_image``
session fixture (which skips if Docker is unavailable or the build fails).

Phase 1 scope — three smoke assertions:
  1. ``test_image_runs_as_nonroot``: container does not run as uid 0.
  2. ``test_image_uid_is_at_least_10000``: uid is >= 10000 (IMAGE-03 gate).
  3. ``test_help_exits_without_traceback``: running the image without required
     env vars produces no Python Traceback on stderr (clean error surfacing).

Phase 2+ adds auth/helm-action smokes; Phase 6 wires these into GHA as required gates.

Note on ``--entrypoint`` override: the image ENTRYPOINT is
``python -m aws_eks_helm_deploy``.  Tests that need to run a system command
(``id``) or a Python one-liner (``python -c "..."``) must use ``--entrypoint``
to bypass the pipe entrypoint; otherwise Docker appends the CMD tokens to the
entrypoint instead of executing a fresh command.
"""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.acceptance
def test_image_runs_as_nonroot(built_image: str) -> None:
    """Container must not run as root (uid 0).

    Uses ``--entrypoint python`` to bypass the pipe entrypoint so the
    ``os.getuid()`` assertion actually executes.  This is the first of the
    IMAGE-03 non-root guards; ``test_image_uid_is_at_least_10000`` is the
    stronger assertion that catches regressions where someone removes ``USER pipe``
    from the Dockerfile but substitutes a different low-uid non-root user.
    """
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "python",
            built_image,
            "-c",
            "import os; assert os.getuid() != 0, f'Running as root! uid={os.getuid()}'",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Expected non-root uid — got:\n{result.stderr}"


@pytest.mark.acceptance
def test_image_uid_is_at_least_10000(built_image: str) -> None:
    """Container uid must be >= 10000 (IMAGE-03: ``adduser --uid 10001``).

    Uses ``--entrypoint id`` to bypass the pipe entrypoint and run ``id -u``
    directly.  Parses stdout and asserts the integer value is at least 10000.
    This gate catches a regression where someone replaces ``USER pipe`` with a
    low-numbered non-root user.
    """
    result = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "id", built_image, "-u"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"id -u failed:\n{result.stderr}"
    uid = int(result.stdout.strip())
    assert uid >= 10000, f"Expected uid >= 10000 (IMAGE-03), got {uid}"


@pytest.mark.acceptance
def test_help_exits_without_traceback(built_image: str) -> None:
    """Running the image without required env vars must not emit a Python traceback.

    Runs the image with its default entrypoint (``python -m aws_eks_helm_deploy``)
    and no env vars set.  This guarantees ``cli.main()`` surfaces errors via
    ``pipe.fail()`` rather than letting unhandled exceptions propagate.

    The specific exit code is NOT asserted here: Phase 1's cli.main() returns 0
    from the placeholder success path (no env-var validation yet); Phase 2+ may
    return non-zero once required env-var validation lands.  The invariant is:
    no ``Traceback (most recent call last):`` on stderr — clean error surfacing
    over raw crash output.
    """
    result = subprocess.run(
        ["docker", "run", "--rm", built_image],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "Traceback" not in result.stderr, (
        f"Python traceback found on stderr — cli.main() must catch all exceptions:\n{result.stderr}"
    )


@pytest.mark.acceptance
def test_curl_purged_from_runtime_image(built_image: str) -> None:
    """curl must not be present in the runtime image (sec-02)."""
    result = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "which", built_image, "curl"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0, "curl should not be present in the runtime image"

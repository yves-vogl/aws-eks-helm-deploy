"""Structural test for .scorecard-exception.md D3 grammar (SEC-10).

Runs the existing `scripts/scorecard-exception-check.py` validator as a
structural test so the grammar gate runs on every push via the unit-coverage
CI job. Previously this lived as a step in `.github/workflows/scorecard.yml`,
but that workflow must stay minimal — `ossf/scorecard-action` rejects any
non-whitelisted step (e.g. `astral-sh/setup-uv`) when `publish_results: true`
(HTTP 400, "workflow verification failed: unallowed step").
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXCEPTION_MD = REPO_ROOT / ".scorecard-exception.md"
CHECKER = REPO_ROOT / "scripts" / "scorecard-exception-check.py"


def test_checker_script_exists() -> None:
    """The D3 grammar validator script must exist."""
    assert CHECKER.is_file(), f"missing: {CHECKER}"


def test_scorecard_exception_grammar_valid() -> None:
    """Run the D3 grammar validator on `.scorecard-exception.md` if present.

    Skips if the file is absent (the exception file is optional — only present
    when an OSSF Scorecard check is intentionally being suppressed).
    """
    if not EXCEPTION_MD.exists():
        pytest.skip("no .scorecard-exception.md present — nothing to validate")
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(EXCEPTION_MD)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f".scorecard-exception.md fails D3 grammar:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

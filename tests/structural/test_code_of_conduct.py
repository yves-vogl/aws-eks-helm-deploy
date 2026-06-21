"""Structural tests for Phase 7 / Plan 07-06 / DOC-07.

Asserts CODE_OF_CONDUCT.md references Contributor Covenant 2.1 with
Reporting + Enforcement sections.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
COC_MD = REPO_ROOT / "CODE_OF_CONDUCT.md"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_code_of_conduct_md_exists() -> None:
    """CODE_OF_CONDUCT.md must exist at the repo root."""
    assert COC_MD.is_file(), f"CODE_OF_CONDUCT.md missing at {COC_MD}"


def test_code_of_conduct_references_contributor_covenant_2_1() -> None:
    """DOC-07: CODE_OF_CONDUCT.md adopts Contributor Covenant version 2.1."""
    text = COC_MD.read_text(encoding="utf-8")
    assert "Contributor Covenant" in text, (
        "CODE_OF_CONDUCT.md must reference the Contributor Covenant (DOC-07)."
    )
    assert "2.1" in text, (
        "CODE_OF_CONDUCT.md must reference Contributor Covenant version 2.1 (DOC-07)."
    )


def test_code_of_conduct_has_reporting_section() -> None:
    """DOC-07: CODE_OF_CONDUCT.md has a ``## Reporting`` section."""
    text = COC_MD.read_text(encoding="utf-8")
    assert "## Reporting" in text, (
        "CODE_OF_CONDUCT.md must contain a `## Reporting` section (DOC-07)."
    )


def test_code_of_conduct_has_enforcement_section() -> None:
    """DOC-07: CODE_OF_CONDUCT.md has a ``## Enforcement`` section."""
    text = COC_MD.read_text(encoding="utf-8")
    assert "## Enforcement" in text, (
        "CODE_OF_CONDUCT.md must contain a `## Enforcement` section (DOC-07)."
    )

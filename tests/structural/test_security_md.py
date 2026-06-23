"""Structural tests for Phase 7 / Plan 07-06 / DOC-06 + D10.

Asserts SECURITY.md contains the 6-month placeholder verbatim (SI-07-07 gate),
the Private Vulnerability Reporting link, and the unchanged 90-day disclosure window.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths and invariants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SECURITY_MD = REPO_ROOT / "SECURITY.md"

# v1.x maintenance policy: NOT maintained — the 6-month security-fix window
# from the original Phase 7 design (D10 / SI-07-07) was dropped post-v2.0.0
# to a clean break. SECURITY.md must say so unambiguously.
V1_NOT_MAINTAINED_WORDING = "Not maintained"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_security_md_exists() -> None:
    """SECURITY.md must exist at the repo root."""
    assert SECURITY_MD.is_file(), f"SECURITY.md missing at {SECURITY_MD}"


def test_security_md_states_v1_not_maintained() -> None:
    """v1.x maintenance policy: NOT maintained.

    The original Phase 7 design assumed a 6-month security-fix window for v1.x
    (D10 / SI-07-07). Policy revised post-v2.0.0 to a clean break — SECURITY.md
    must say "Not maintained" so readers don't expect patches.
    """
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert V1_NOT_MAINTAINED_WORDING in text, (
        f"SECURITY.md must contain `{V1_NOT_MAINTAINED_WORDING}` in the v1.x "
        "supported-versions row (post-v2.0.0 policy: v1.x has no maintenance window)."
    )


def test_security_md_has_pvr_link() -> None:
    """SECURITY.md must surface a Private Vulnerability Reporting channel."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "Private Vulnerability Reporting" in text or "security/advisories/new" in text, (
        "SECURITY.md must reference GitHub Private Vulnerability Reporting "
        "(either by name or via the security/advisories/new link)."
    )


def test_security_md_disclosure_timeline_unchanged() -> None:
    """D10 constraint: the 90-day coordinated disclosure window stays unchanged."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "Day 90 (max)" in text, (
        "SECURITY.md disclosure timeline must keep the 'Day 90 (max)' marker "
        "(D10: 90-day window unchanged)."
    )


def test_security_md_has_scope_section() -> None:
    """DOC-06 + Phase 6 governance: SECURITY.md must have a Scope section."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "## Scope" in text, (
        "SECURITY.md must contain a `## Scope` section (DOC-06 / Phase 6 governance)."
    )
